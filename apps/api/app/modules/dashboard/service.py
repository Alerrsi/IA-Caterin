"""Tablero del negocio para la dueña (T17).

- Las consultas usan la sesión de tenant (`core/tenancy.py`), que filtra por `pyme_id`: aquí no se filtra a mano.
- La agregación son funciones puras sobre `Decimal` (sin base de datos), para probarlas directo.
- Supuestos de negocio (venta = cotización aceptada, mes del evento, margen sobre insumos): docs/tasks/T17-tablero.md.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Date, cast, func, select
from sqlalchemy.orm import Session

from app.core.money import quantize_clp
from app.db.enums import OrderStatus, OrderUnit, QuoteStatus
from app.db.models import Ingredient, Order, OrderLine, Quote, QuoteLine, Recipe, Supplier
from app.modules.dashboard.schemas import (
    Dashboard,
    DashboardKpis,
    DashboardPeriod,
    DayLoad,
    LowStock,
    LowStockItem,
    MonthSales,
    StatusCount,
    SupplierSpend,
    TopProduct,
    TopProducts,
)

TZ = ZoneInfo("America/Santiago")
SOLD = (OrderStatus.CONFIRMED, OrderStatus.DELIVERED)
OPEN = (OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.REQUESTED)
# Orden fijo de los estados en el gráfico (el embudo del pedido). Los borradores del portal no los ve la pyme.
STATUS_ORDER = (
    OrderStatus.REQUESTED,
    OrderStatus.DRAFT,
    OrderStatus.CONFIRMED,
    OrderStatus.DELIVERED,
    OrderStatus.CANCELLED,
)
UNIT_FACTOR = {OrderUnit.UNIT: Decimal(1), OrderUnit.PORTION: Decimal(1), OrderUnit.DOZEN: Decimal(12)}
UPCOMING_DAYS = 14
TOP_PRODUCTS = 8
TOP_SUPPLIERS = 5
LOW_STOCK_ITEMS = 8
OTHERS = "Otros"


# --------------------------------------------------------------------------- periodo


def local_today() -> date:
    return datetime.now(TZ).date()


def _add_months(first: date, n: int) -> date:
    index = first.year * 12 + first.month - 1 + n
    return date(index // 12, index % 12 + 1, 1)


def window(today: date, months: int) -> tuple[date, date]:
    """Del primer día de hace `months - 1` meses al último día del mes en curso."""
    this_month = today.replace(day=1)
    return _add_months(this_month, -(months - 1)), _add_months(this_month, 1) - timedelta(days=1)


def month_keys(date_from: date, months: int) -> list[str]:
    return [_add_months(date_from, i).strftime("%Y-%m") for i in range(months)]


# --------------------------------------------------------------------------- agregación pura


@dataclass(frozen=True)
class SoldOrder:
    """Un pedido confirmado o entregado, con su cotización aceptada (o sin ella)."""

    day: date
    net: Decimal | None
    cost: Decimal | None
    total: Decimal | None

    @property
    def has_quote(self) -> bool:
        return self.total is not None


def _clp(value: Decimal) -> int:
    return int(quantize_clp(value))


def sales_by_month(orders: Iterable[SoldOrder], keys: Sequence[str]) -> list[MonthSales]:
    """Todos los meses del periodo, aunque estén en cero (un mes sin ventas también es un dato)."""
    acc: dict[str, list[Decimal]] = {k: [Decimal(0)] * 4 for k in keys}  # pedidos, neto, costo, total
    for o in orders:
        key = o.day.strftime("%Y-%m")
        if key not in acc or not o.has_quote:
            continue
        row = acc[key]
        row[0] += 1
        row[1] += o.net or 0
        row[2] += o.cost or 0
        row[3] += o.total or 0
    return [
        MonthSales(
            month=k,
            orders=int(r[0]),
            net_clp=_clp(r[1]),
            ingredients_cost_clp=_clp(r[2]),
            margin_clp=_clp(r[1] - r[2]),
            total_clp=_clp(r[3]),
        )
        for k, r in acc.items()
    ]


def sales_kpis(orders: Sequence[SoldOrder]) -> dict[str, int | float | None]:
    sold = [o for o in orders if o.has_quote]
    net = sum((o.net or Decimal(0) for o in sold), Decimal(0))
    cost = sum((o.cost or Decimal(0) for o in sold), Decimal(0))
    total = sum((o.total or Decimal(0) for o in sold), Decimal(0))
    margin = net - cost
    return {
        "sales_total_clp": _clp(total),
        "sales_net_clp": _clp(net),
        "ingredients_cost_clp": _clp(cost),
        "margin_clp": _clp(margin),
        "margin_pct": float((margin * 100 / net).quantize(Decimal("0.1"))) if net > 0 else None,
        "sold_orders": len(sold),
        "avg_ticket_clp": _clp(total / len(sold)) if sold else None,
        "orders_without_quote": len(orders) - len(sold),
    }


@dataclass(frozen=True)
class ProductLine:
    order_id: uuid.UUID
    recipe_id: uuid.UUID
    name: str
    qty: Decimal
    unit: OrderUnit


def top_products(lines: Iterable[ProductLine], limit: int = TOP_PRODUCTS) -> TopProducts:
    units: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    orders: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    names: dict[uuid.UUID, str] = {}
    excluded = 0
    for line in lines:
        factor = UNIT_FACTOR.get(line.unit)
        if factor is None:
            excluded += 1
            continue
        units[line.recipe_id] += line.qty * factor
        orders[line.recipe_id].add(line.order_id)
        names[line.recipe_id] = line.name
    ranked = sorted(units, key=lambda rid: (-units[rid], names[rid].lower()))[:limit]
    items = [
        TopProduct(recipe_id=rid, name=names[rid], units=_qty(units[rid]), orders=len(orders[rid])) for rid in ranked
    ]
    return TopProducts(items=items, excluded_lines=excluded)


def supplier_spend(rows: Iterable[tuple[uuid.UUID, str, Decimal]], limit: int = TOP_SUPPLIERS) -> list[SupplierSpend]:
    """Los `limit` proveedores con más compra estimada y el resto sumado en «Otros»."""
    ranked = sorted((r for r in rows if r[2] > 0), key=lambda r: (-r[2], r[1].lower()))
    out = [SupplierSpend(supplier_id=sid, name=name, amount_clp=_clp(amount)) for sid, name, amount in ranked[:limit]]
    rest = sum((r[2] for r in ranked[limit:]), Decimal(0))
    if rest > 0:
        out.append(SupplierSpend(supplier_id=None, name=OTHERS, amount_clp=_clp(rest)))
    return out


def _qty(value: Decimal) -> str:
    """Decimal sin ceros sobrantes y sin notación científica ("24", "2.5")."""
    text = format(value.normalize(), "f")
    return text


def pct_of_min(stock: Decimal, minimum: Decimal) -> float:
    if minimum <= 0:
        return 100.0
    return float(max(stock, Decimal(0)) * 100 / minimum)


# --------------------------------------------------------------------------- consultas


def _order_day() -> ColumnElement[date]:
    """Fecha del evento o, si falta, el día local en que se creó el pedido."""
    return func.coalesce(Order.event_date, cast(func.timezone(str(TZ), Order.created_at), Date))


def _sold_orders(db: Session, date_from: date, date_to: date) -> tuple[list[SoldOrder], dict[uuid.UUID, uuid.UUID]]:
    """Pedidos vendidos del periodo y, para cada uno con cotización aceptada, el id de esa cotización."""
    day = _order_day()
    rows = db.execute(select(Order.id, day).where(Order.status.in_(SOLD), day >= date_from, day <= date_to)).all()
    order_days: dict[uuid.UUID, date] = {r[0]: r[1] for r in rows}
    chosen: dict[uuid.UUID, Quote] = {}
    if order_days:
        quotes = db.scalars(
            select(Quote).where(Quote.order_id.in_(order_days), Quote.status == QuoteStatus.ACCEPTED)
        ).all()
        for q in quotes:
            prev = chosen.get(q.order_id)
            if prev is None or q.version > prev.version:
                chosen[q.order_id] = q
    sold = []
    for oid, d in order_days.items():
        best = chosen.get(oid)
        sold.append(
            SoldOrder(
                day=d,
                net=best.net_clp if best else None,
                cost=best.ingredients_cost_clp if best else None,
                total=best.total_clp if best else None,
            )
        )
    return sold, {oid: q.id for oid, q in chosen.items()}


def _orders_by_status(db: Session, date_from: date, date_to: date) -> list[StatusCount]:
    day = _order_day()
    counts = dict(
        db.execute(
            select(Order.status, func.count())
            .where(Order.status.in_(STATUS_ORDER), day >= date_from, day <= date_to)
            .group_by(Order.status)
        ).all()
    )
    return [StatusCount(status=s.value, orders=int(counts.get(s, 0))) for s in STATUS_ORDER]


def _product_lines(db: Session, date_from: date, date_to: date) -> list[ProductLine]:
    day = _order_day()
    rows = db.execute(
        select(OrderLine.order_id, OrderLine.recipe_id, Recipe.name, OrderLine.qty, OrderLine.unit)
        .join(Order, (Order.id == OrderLine.order_id) & (Order.pyme_id == OrderLine.pyme_id))
        .join(Recipe, (Recipe.id == OrderLine.recipe_id) & (Recipe.pyme_id == OrderLine.pyme_id))
        .where(Order.status.in_(SOLD), day >= date_from, day <= date_to)
    ).all()
    return [
        ProductLine(order_id=r[0], recipe_id=r[1], name=r[2], qty=r[3], unit=r[4]) for r in rows if r[1] is not None
    ]


def _supplier_rows(db: Session, quote_ids: Sequence[uuid.UUID]) -> list[tuple[uuid.UUID, str, Decimal]]:
    if not quote_ids:
        return []
    rows = db.execute(
        select(Supplier.id, Supplier.name, func.sum(QuoteLine.subtotal_clp))
        .join(Supplier, (Supplier.id == QuoteLine.supplier_id) & (Supplier.pyme_id == QuoteLine.pyme_id))
        .where(QuoteLine.quote_id.in_(quote_ids))
        .group_by(Supplier.id, Supplier.name)
    ).all()
    return [(r[0], r[1], Decimal(r[2] or 0)) for r in rows]


def _upcoming(db: Session, today: date) -> list[DayLoad]:
    last = today + timedelta(days=UPCOMING_DAYS - 1)
    rows = db.execute(
        select(Order.event_date, Order.status, Order.guests).where(
            Order.status.in_(OPEN), Order.event_date >= today, Order.event_date <= last
        )
    ).all()
    days = {today + timedelta(days=i): [0, 0, 0] for i in range(UPCOMING_DAYS)}  # confirmados, por confirmar, invitados
    for event_date, status, guests in rows:
        if event_date is None:
            continue
        acc = days[event_date]
        acc[0 if status == OrderStatus.CONFIRMED else 1] += 1
        acc[2] += guests or 0
    return [DayLoad(day=d, confirmed=a[0], pending=a[1], guests=a[2]) for d, a in days.items()]


def _low_stock(db: Session) -> LowStock:
    rows = db.scalars(
        select(Ingredient).where(
            Ingredient.is_active.is_(True),
            Ingredient.min_stock_qty.is_not(None),
            Ingredient.stock_qty < Ingredient.min_stock_qty,
        )
    ).all()
    items = sorted(
        (
            LowStockItem(
                ingredient_id=i.id,
                name=i.name,
                base_unit=i.base_unit.value,
                stock_qty=_qty(i.stock_qty),
                min_stock_qty=_qty(i.min_stock_qty or Decimal(0)),
                pct_of_min=round(pct_of_min(i.stock_qty, i.min_stock_qty or Decimal(0)), 1),
            )
            for i in rows
        ),
        key=lambda x: (x.pct_of_min, x.name.lower()),
    )
    return LowStock(items=items[:LOW_STOCK_ITEMS], total=len(items))


def _count(db: Session, *where: ColumnElement[bool]) -> int:
    return int(db.scalar(select(func.count()).select_from(Order).where(*where)) or 0)


def build_dashboard(db: Session, months: int, today: date | None = None) -> Dashboard:
    today = today or local_today()
    date_from, date_to = window(today, months)
    sold, chosen = _sold_orders(db, date_from, date_to)
    low = _low_stock(db)
    upcoming = _upcoming(db, today)
    week = today + timedelta(days=6)
    kpis = DashboardKpis(
        **sales_kpis(sold),
        pending_requests=_count(db, Order.status == OrderStatus.REQUESTED),
        upcoming_7d=sum(d.confirmed + d.pending for d in upcoming if d.day <= week),
        low_stock=low.total,
    )
    return Dashboard(
        period=DashboardPeriod(months=months, date_from=date_from, date_to=date_to, today=today),
        kpis=kpis,
        sales_by_month=sales_by_month(sold, month_keys(date_from, months)),
        orders_by_status=_orders_by_status(db, date_from, date_to),
        top_products=top_products(_product_lines(db, date_from, date_to)),
        upcoming_by_day=upcoming,
        spend_by_supplier=supplier_spend(_supplier_rows(db, list(chosen.values()))),
        low_stock=low,
        generated_at=datetime.now(UTC),
    )

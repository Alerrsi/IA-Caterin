"""Pedidos y cotizaciones (F3). La aritmética vive en `calculator.py`; aquí se carga, guarda y traza."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.llm import LLMProvider
from app.core.money import quantize_clp
from app.core.tenancy import CurrentUser
from app.db.enums import DataDomain, MetricKind, OrderStatus, OrderUnit, QuoteStatus, Role
from app.db.models import Ingredient, MetricEvent, Order, OrderLine, Pyme, Quote, QuoteLine, Recipe, Supplier
from app.modules.quotes.calculator import (
    ORDER_UNIT_LABELS,
    IngredientInfo,
    ProductRequest,
    PurchaseChoice,
    QuoteCalculationError,
    QuoteParams,
    QuoteResult,
    RecipeInfo,
    RecipeLineInfo,
    calculate_quote,
)
from app.modules.quotes.extractor import extract_order
from app.modules.quotes.pdf import quote_number, render_quote_pdf
from app.modules.quotes.schemas import (
    ExtractionOut,
    OrderCreate,
    OrderLineIn,
    OrderLineOut,
    OrderOut,
    OrderUpdate,
    PurchaseOut,
    QuoteCreate,
    QuoteLineOut,
    QuoteOut,
    QuoteProductOut,
    ShoppingGroup,
    ShoppingItem,
    ShoppingList,
)
from app.modules.recipes.costing import PriceOption
from app.modules.suppliers.service import current_options

MAX_TIMING_S = 24 * 3600


# --------------------------------------------------------------------------- pedidos


def _recipes(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Recipe]:
    found = {r.id: r for r in db.scalars(select(Recipe).where(Recipe.id.in_(ids)))}
    missing = [i for i in ids if i not in found]
    if missing:
        raise ProblemError(422, "recipe_not_found", "Uno de los productos no corresponde a una receta tuya")
    return found


def build_lines(db: Session, lines: list[OrderLineIn]) -> list[OrderLine]:
    recipes = _recipes(db, list({line.recipe_id for line in lines}))
    return [
        OrderLine(
            recipe_id=line.recipe_id,
            position=pos,
            requested_name=(line.requested_name or recipes[line.recipe_id].name).strip(),
            qty=line.qty,
            unit=line.unit,
        )
        for pos, line in enumerate(lines)
    ]


def list_orders(db: Session, status: OrderStatus | None, upcoming_days: int | None, today: date) -> list[Order]:
    # Lo que un cliente cotizó y no envió es suyo: la pyme no lo ve (ADR-007).
    stmt = (
        select(Order)
        .where(Order.status != OrderStatus.CUSTOMER_DRAFT)
        .order_by(Order.event_date.asc().nulls_last(), Order.created_at.desc())
    )
    if status:
        stmt = stmt.where(Order.status == status)
    if upcoming_days is not None:
        stmt = stmt.where(
            Order.event_date >= today,
            Order.event_date <= today + timedelta(days=upcoming_days),
            Order.status.in_([OrderStatus.DRAFT, OrderStatus.CONFIRMED]),
        )
    return list(db.scalars(stmt.limit(200)))


def get_order(db: Session, order_id: uuid.UUID, include_customer_drafts: bool = False) -> Order:
    order = db.get(Order, order_id)
    if order is None or (order.status == OrderStatus.CUSTOMER_DRAFT and not include_customer_drafts):
        raise not_found("order_not_found", "No encontramos ese pedido")
    return order


def create_order(db: Session, data: OrderCreate) -> Order:
    order = Order(**data.model_dump(exclude={"lines"}))
    order.customer_name = order.customer_name.strip()
    db.add(order)
    db.flush()
    for line in build_lines(db, data.lines):
        line.pyme_id, line.order_id = order.pyme_id, order.id
        db.add(line)
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(order)
    return order


def update_order(db: Session, order_id: uuid.UUID, data: OrderUpdate) -> Order:
    order = get_order(db, order_id)
    changes = data.model_dump(exclude_unset=True, exclude={"lines"})
    for field, value in changes.items():
        if value is None and field in ("customer_name", "status"):
            continue
        setattr(order, field, value)
    if data.lines is not None:
        new_lines = build_lines(db, data.lines)
        order.lines.clear()
        db.flush()
        order.lines.extend(new_lines)
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(order)
    return order


def order_out(db: Session, order: Order) -> OrderOut:
    out = OrderOut.model_validate(order)
    ids = [line.recipe_id for line in out.lines if line.recipe_id]
    names = dict(db.execute(select(Recipe.id, Recipe.name).where(Recipe.id.in_(ids))).all()) if ids else {}
    lines: list[OrderLineOut] = []
    for line in out.lines:
        line.recipe_name = names.get(line.recipe_id) if line.recipe_id else None
        lines.append(line)
    out.lines = lines
    out.from_customer = order.customer_user_id is not None
    out.last_quote_id = db.scalar(
        select(Quote.id).where(Quote.order_id == order.id).order_by(Quote.version.desc()).limit(1)
    )
    return out


def extract(llm: LLMProvider, text: str, choices: dict[uuid.UUID, str], today: date) -> ExtractionOut:
    """Lee un pedido escrito contra `choices` (recetas de la pyme, o productos del portal). No guarda nada."""
    return extract_order(llm, text, choices, today)


def pdf(quote: Quote, order: Order, pyme: Pyme) -> tuple[bytes, str]:
    """El PDF para el cliente final y su nombre de archivo."""
    return render_quote_pdf(quote, order, pyme), f"{quote_number(quote)}.pdf"


def unit_label(unit: OrderUnit, qty: Decimal) -> str:
    singular, plural = ORDER_UNIT_LABELS[unit]
    return singular if qty == 1 else plural


def latest_quote(db: Session, order_id: uuid.UUID) -> Quote | None:
    return db.scalar(select(Quote).where(Quote.order_id == order_id).order_by(Quote.version.desc()).limit(1))


def decide_request(db: Session, order_id: uuid.UUID, accept: bool, message: str | None) -> Order:
    """La dueña acepta o rechaza lo que envió un cliente del portal (ADR-007).

    Aceptar: el pedido queda confirmado y su última cotización (si está completa) aceptada.
    Rechazar: el pedido queda cancelado y la cotización rechazada. El mensaje lo ve el cliente.
    """
    order = get_order(db, order_id)
    if order.status != OrderStatus.REQUESTED:
        raise ProblemError(409, "not_a_request", "Este pedido no es una solicitud pendiente de un cliente")
    quote = latest_quote(db, order.id)
    if accept:
        if quote is None or not quote.is_complete:
            raise ProblemError(
                409,
                "quote_incomplete",
                "Primero calcula una cotización completa",
                (missing_detail(quote) if quote else "El pedido aún no tiene cotización.")
                + " Así el cliente ve el precio que aceptas.",
            )
        order.status, quote.status = OrderStatus.CONFIRMED, QuoteStatus.ACCEPTED
    else:
        order.status = OrderStatus.CANCELLED
        if quote is not None:
            quote.status = QuoteStatus.REJECTED
    order.decided_at = datetime.now(UTC)
    order.owner_message = message.strip() if message and message.strip() else None
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(order)
    return order


def recipe_choices(db: Session) -> dict[uuid.UUID, str]:
    return dict(db.execute(select(Recipe.id, Recipe.name).where(Recipe.is_active)).all())


# --------------------------------------------------------------------------- cotizaciones


def _load_inputs(
    db: Session, order: Order
) -> tuple[list[ProductRequest], dict[uuid.UUID, IngredientInfo], dict[uuid.UUID, list[PriceOption]]]:
    unresolved = [line.requested_name for line in order.lines if line.recipe_id is None]
    if unresolved:
        raise ProblemError(
            422,
            "unresolved_products",
            "Hay productos sin receta asociada",
            "Elige la receta de: " + ", ".join(unresolved),
        )
    recipes = _recipes(db, list({line.recipe_id for line in order.lines if line.recipe_id}))
    ing_ids = list({rl.ingredient_id for r in recipes.values() for rl in r.lines})
    ingredients = {
        i.id: IngredientInfo(i.id, i.name, i.base_unit, i.stock_qty, i.waste_pct)
        for i in db.scalars(select(Ingredient).where(Ingredient.id.in_(ing_ids)))
    }
    infos = {
        r.id: RecipeInfo(
            r.id,
            r.name,
            r.version,
            r.yield_qty,
            r.yield_unit,
            [RecipeLineInfo(rl.ingredient_id, rl.qty, rl.waste_pct) for rl in r.lines],
        )
        for r in recipes.values()
    }
    empty = [r.name for r in recipes.values() if not r.lines]
    if empty:
        raise ProblemError(422, "empty_recipe", "Una receta no tiene insumos", ", ".join(empty))
    products = [
        ProductRequest(infos[line.recipe_id], line.requested_name, line.qty, line.unit)
        for line in order.lines
        if line.recipe_id
    ]
    return products, ingredients, current_options(db, ing_ids)


def _purchase_json(choice: PurchaseChoice, vat: Decimal) -> dict[str, Any]:
    o = choice.option
    return {
        "price_id": str(o.price_id),
        "supplier_id": str(o.supplier_id),
        "supplier_name": o.supplier_name,
        "package_label": o.package_label,
        "package_qty": str(o.package_qty),
        "packages": choice.packages,
        "package_price_clp": int(quantize_clp(o.gross_price(vat))),
        "total_clp": int(choice.total_clp),
        "price_date": o.price_date.isoformat(),
    }


def _snapshot(result: QuoteResult) -> dict[str, Any]:
    """La "versión de precios" usada: cada precio que intervino, con sus valores de ese momento."""
    snap: dict[str, Any] = {}
    for r in result.ingredients:
        used = [r.cheapest] if r.cheapest else []
        used += [c.option for c in ([r.purchase] if r.purchase else []) + r.alternatives]
        for o in used:
            snap[str(o.price_id)] = {
                "ingredient_id": str(r.ingredient.id),
                "supplier_id": str(o.supplier_id),
                "supplier_name": o.supplier_name,
                "package_label": o.package_label,
                "package_qty": str(o.package_qty),
                "price_clp": int(o.price_clp),
                "includes_vat": o.includes_vat,
                "price_date": o.price_date.isoformat(),
            }
    return snap


def stock_check(db: Session, order: Order) -> QuoteResult:
    """Insumos que pide el pedido frente al stock de hoy, con las mismas reglas de merma que la cotización.

    Solo mira cantidades (el margen no influye). No guarda nada. Lanza ProblemError o QuoteCalculationError
    si el pedido no se puede calcular. Lo usa el asistente ("¿me alcanza para el pedido del sábado?")."""
    pyme = db.get(Pyme, db.info["pyme_id"])
    assert pyme is not None  # noqa: S101
    products, ingredients, options = _load_inputs(db, order)
    params = QuoteParams(Decimal(0), pyme.vat_pct, pyme.default_waste_pct, use_stock=True)
    return calculate_quote(products, ingredients, options, params)


def create_quote(db: Session, user: CurrentUser, order_id: uuid.UUID, data: QuoteCreate, today: date) -> Quote:
    order = get_order(db, order_id, include_customer_drafts=user.role == Role.CUSTOMER)
    if order.status == OrderStatus.CANCELLED:
        raise ProblemError(409, "order_cancelled", "El pedido está cancelado")
    pyme = db.get(Pyme, user.pyme_id)
    assert pyme is not None  # noqa: S101
    margin = data.margin_pct if data.margin_pct is not None else pyme.default_margin_pct
    if margin is None:
        raise ProblemError(
            422, "margin_required", "Falta tu margen de ganancia", "Defínelo en la configuración o en esta cotización."
        )
    products, ingredients, options = _load_inputs(db, order)
    params = QuoteParams(margin, pyme.vat_pct, pyme.default_waste_pct, data.use_stock)
    try:
        result = calculate_quote(products, ingredients, options, params)
    except QuoteCalculationError as exc:
        raise ProblemError(422, "quote_calculation", "No se puede calcular este pedido", str(exc)) from exc

    version = (db.scalar(select(func.max(Quote.version)).where(Quote.order_id == order.id)) or 0) + 1
    vat = pyme.vat_pct
    quote = Quote(
        order_id=order.id,
        version=version,
        status=QuoteStatus.DRAFT,
        price_snapshot=_snapshot(result),
        assumptions={
            "margin_pct": str(margin),
            "vat_pct": str(vat),
            "default_waste_pct": str(pyme.default_waste_pct),
            "use_stock": data.use_stock,
            "costs_include_vat": True,
            "price_choice_for_cost": "presentación vigente más barata por unidad base",
            "price_choice_for_purchase": "presentación con menor total a pagar",
            "rounding": "cantidades a 3 decimales; pesos mitad hacia arriba por producto, IVA sobre el neto",
            "stock_snapshot": {str(i.id): str(i.stock_qty) for i in ingredients.values()},
            "missing_prices": result.missing_prices,
            "shopping_total_clp": int(result.shopping_total_clp),
            "products": [
                {
                    "recipe_id": str(p.recipe_id),
                    "recipe_name": p.recipe_name,
                    "recipe_version": p.recipe_version,
                    "requested_name": p.requested_name,
                    "qty": str(p.qty),
                    "unit": p.unit.value,
                    "unit_label": p.unit_label,
                    "cost_clp": int(p.cost_clp) if p.cost_clp is not None else None,
                    "unit_price_clp": int(p.unit_price_clp) if p.unit_price_clp is not None else None,
                    "subtotal_clp": int(p.subtotal_clp) if p.subtotal_clp is not None else None,
                }
                for p in result.products
            ],
        },
        ingredients_cost_clp=result.ingredients_cost_clp,
        margin_pct=margin,
        net_clp=result.net_clp,
        vat_clp=result.vat_clp,
        total_clp=result.total_clp,
        is_complete=result.is_complete,
        calc_version=result.calc_version,
        valid_until=today + timedelta(days=pyme.quote_validity_days) if pyme.quote_validity_days else None,
    )
    db.add(quote)
    db.flush()
    for pos, r in enumerate(result.ingredients):
        chosen = r.purchase.option if r.purchase else r.cheapest
        db.add(
            QuoteLine(
                quote_id=quote.id,
                ingredient_id=r.ingredient.id,
                position=pos,
                required_qty=r.required_qty,
                stock_used_qty=r.stock_used_qty,
                to_buy_qty=r.to_buy_qty,
                ingredient_price_id=chosen.price_id if chosen else None,
                supplier_id=r.purchase.option.supplier_id if r.purchase else None,
                packages_to_buy=r.purchase.packages if r.purchase else 0,
                unit_price_clp=quantize_clp(r.purchase.option.gross_price(vat)) if r.purchase else None,
                subtotal_clp=r.purchase.total_clp if r.purchase else Decimal(0),
                price_date=r.purchase.option.price_date if r.purchase else None,
                alternatives=[_purchase_json(c, vat) for c in r.alternatives],
                note=r.note,
            )
        )
    if data.started_at is not None:
        elapsed = (datetime.now(UTC) - data.started_at.astimezone(UTC)).total_seconds()
        if 0 <= elapsed <= MAX_TIMING_S:
            db.add(
                MetricEvent(
                    user_id=user.id,
                    kind=MetricKind.QUOTE_TIMING,
                    value_num=Decimal(str(round(elapsed, 1))),
                    payload={"quote_id": str(quote.id), "order_id": str(order.id), "source": order.source.value},
                )
            )
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(quote)
    return quote


def get_quote(db: Session, quote_id: uuid.UUID) -> Quote:
    """Para la pyme: la cotización de un pedido que el cliente aún no envía no existe para ella."""
    quote = db.get(Quote, quote_id)
    if quote is None or db.scalar(select(Order.status).where(Order.id == quote.order_id)) == OrderStatus.CUSTOMER_DRAFT:
        raise not_found("quote_not_found", "No encontramos esa cotización")
    return quote


def list_quotes(db: Session, order_id: uuid.UUID) -> list[Quote]:
    get_order(db, order_id)
    return list(db.scalars(select(Quote).where(Quote.order_id == order_id).order_by(Quote.version.desc())))


def update_quote_status(db: Session, quote_id: uuid.UUID, status: QuoteStatus) -> Quote:
    quote = get_quote(db, quote_id)
    if status in (QuoteStatus.SENT, QuoteStatus.ACCEPTED) and not quote.is_complete:
        raise ProblemError(409, "quote_incomplete", "La cotización está incompleta", missing_detail(quote))
    quote.status = status
    if status == QuoteStatus.ACCEPTED:
        order = get_order(db, quote.order_id)
        if order.status == OrderStatus.REQUESTED:  # aceptar la cotización acepta la solicitud del cliente
            order.decided_at = datetime.now(UTC)
        if order.status in (OrderStatus.DRAFT, OrderStatus.REQUESTED):
            order.status = OrderStatus.CONFIRMED
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(quote)
    return quote


def missing_detail(quote: Quote) -> str:
    missing = quote.assumptions.get("missing_prices") or []
    return "Falta el precio de: " + ", ".join(missing) if missing else "Faltan datos para calcularla."


def quote_out(db: Session, quote: Quote) -> QuoteOut:
    ing_ids = [line.ingredient_id for line in quote.lines]
    ingredients = {i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.id.in_(ing_ids)))}
    sup_ids = [line.supplier_id for line in quote.lines if line.supplier_id]
    suppliers = dict(db.execute(select(Supplier.id, Supplier.name).where(Supplier.id.in_(sup_ids))).all())
    snap = quote.price_snapshot
    lines = []
    for line in quote.lines:
        purchase = None
        if line.supplier_id and line.ingredient_price_id:
            p = snap[str(line.ingredient_price_id)]
            purchase = PurchaseOut(
                price_id=line.ingredient_price_id,
                supplier_id=line.supplier_id,
                supplier_name=suppliers.get(line.supplier_id, p["supplier_name"]),
                package_label=p["package_label"],
                package_qty=Decimal(p["package_qty"]),
                packages=line.packages_to_buy,
                package_price_clp=int(line.unit_price_clp or 0),
                total_clp=int(line.subtotal_clp),
                price_date=date.fromisoformat(p["price_date"]),
            )
        ing = ingredients[line.ingredient_id]
        lines.append(
            QuoteLineOut(
                ingredient_id=line.ingredient_id,
                ingredient_name=ing.name,
                base_unit=ing.base_unit.value,
                required_qty=line.required_qty,
                stock_used_qty=line.stock_used_qty,
                to_buy_qty=line.to_buy_qty,
                purchase=purchase,
                alternatives=[PurchaseOut.model_validate(a) for a in line.alternatives],
                note=line.note,
            )
        )
    a = quote.assumptions
    return QuoteOut(
        id=quote.id,
        order_id=quote.order_id,
        version=quote.version,
        status=quote.status,
        created_at=quote.created_at,
        valid_until=quote.valid_until,
        margin_pct=quote.margin_pct,
        vat_pct=Decimal(a["vat_pct"]),
        use_stock=bool(a["use_stock"]),
        is_complete=quote.is_complete,
        missing_prices=list(a.get("missing_prices", [])),
        ingredients_cost_clp=int(quote.ingredients_cost_clp),
        net_clp=int(quote.net_clp),
        vat_clp=int(quote.vat_clp),
        total_clp=int(quote.total_clp),
        shopping_total_clp=int(a.get("shopping_total_clp", 0)),
        calc_version=quote.calc_version,
        products=[QuoteProductOut.model_validate(p) for p in a["products"]],
        lines=lines,
    )


def shopping_list(db: Session, quote: Quote) -> ShoppingList:
    out = quote_out(db, quote)
    sup_ids = [line.purchase.supplier_id for line in out.lines if line.purchase]
    suppliers = {s.id: s for s in db.scalars(select(Supplier).where(Supplier.id.in_(sup_ids)))}
    groups: dict[uuid.UUID, ShoppingGroup] = {}
    for line in out.lines:
        if not line.purchase:
            continue
        p = line.purchase
        sup = suppliers.get(p.supplier_id)
        group = groups.setdefault(
            p.supplier_id,
            ShoppingGroup(
                supplier_id=p.supplier_id,
                supplier_name=p.supplier_name,
                delivery_days=sup.delivery_days if sup else None,
                phone=sup.phone if sup else None,
                items=[],
                total_clp=0,
            ),
        )
        group.items.append(
            ShoppingItem(
                ingredient_name=line.ingredient_name,
                package_label=p.package_label,
                packages=p.packages,
                package_price_clp=p.package_price_clp,
                total_clp=p.total_clp,
                price_date=p.price_date,
            )
        )
        group.total_clp += p.total_clp
    ordered = sorted(groups.values(), key=lambda g: g.supplier_name.lower())
    return ShoppingList(
        quote_id=quote.id,
        groups=ordered,
        without_price=[ln.ingredient_name for ln in out.lines if ln.to_buy_qty > 0 and not ln.purchase],
        covered_by_stock=[ln.ingredient_name for ln in out.lines if ln.to_buy_qty == 0],
        total_clp=sum(g.total_clp for g in ordered),
    )

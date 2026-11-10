"""Consultas tipadas de solo lectura del asistente (AGENTS.md sección 4). Filtran por pyme por la sesión de tenant.

Cada una resuelve entidades en código y devuelve la respuesta de nivel 0 ya redactada con plantilla: los números
salen de los servicios de T04/T05, nunca de un LLM. Si no hay dato, lo dice.
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.dates import parse_event_date
from app.core.errors import ProblemError
from app.core.money import format_clp
from app.core.units import BASE_UNIT_LABELS, format_decimal, human_qty
from app.db.enums import BaseUnit, OrderStatus
from app.db.models import Ingredient, Order, ProductionRecord, Recipe, Supplier
from app.modules.assistant.entities import find_entity
from app.modules.assistant.parsing import WEEKDAYS_LONG, fmt_date, parse_past_range, parse_qty, parse_range
from app.modules.assistant.recognizer import normalize_question
from app.modules.quotes import service as quotes
from app.modules.quotes.calculator import ORDER_UNIT_LABELS, QuoteCalculationError
from app.modules.recipes import service as recipes
from app.modules.suppliers import service as suppliers

TZ = ZoneInfo("America/Santiago")
ACTIVE_ORDERS = (OrderStatus.DRAFT, OrderStatus.CONFIRMED)

MAX_LIST = 8
Status = Literal["ok", "no_data", "ambiguous", "missing_entity"]
ORDER_STATUS_ES = {OrderStatus.DRAFT: "borrador", OrderStatus.CONFIRMED: "confirmado"}


@dataclass
class QueryResult:
    status: Status
    text: str
    sources: list[dict[str, str]] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)
    options: list[dict[str, str]] = field(default_factory=list)  # botones para elegir cuando hay ambigüedad


def _src(kind: str, label: str) -> list[dict[str, str]]:
    return [{"kind": kind, "label": label}]


def _resolve(
    kind: str, text: str, choices: dict[uuid.UUID, str], ask: Callable[[str], str], noun: str
) -> tuple[uuid.UUID | None, QueryResult | None]:
    """Devuelve el id encontrado o, si no hay uno claro, la respuesta que pide aclarar (nunca adivina)."""
    m = find_entity(text, choices)
    if m.match:
        return m.match.id, None
    if m.suggestions:
        opts = [{"label": c.name, "question": ask(c.name)} for c in m.suggestions]
        return None, QueryResult("ambiguous", f"¿A cuál {noun} te refieres?", options=opts)
    return None, QueryResult("missing_entity", f"No encontré ese {noun} en tus datos. ¿Me dices cómo se llama?")


def get_stock(db: Session, text: str, today: date) -> QueryResult:
    choices = {i.id: i.name for i in db.scalars(select(Ingredient).where(Ingredient.is_active))}
    found, ask = _resolve("ingredient", text, choices, lambda n: f"¿Cuánto me queda de {n}?", "insumo")
    if found is None:
        return ask  # type: ignore[return-value]
    ing = db.get(Ingredient, found)
    assert ing is not None  # noqa: S101 - salió del mismo catálogo de la pyme
    qty = human_qty(ing.stock_qty, ing.base_unit)
    out = f"No te queda {ing.name} (stock en 0)." if ing.stock_qty <= 0 else f"Te quedan {qty} de {ing.name}."
    if _is_low(ing) and ing.stock_qty > 0:
        out += f" Está bajo tu mínimo de {human_qty(ing.min_stock_qty or Decimal(0), ing.base_unit)}."
    return QueryResult("ok", out, _src("inventory", "tu inventario"), {"item": ing.name})


def list_low_stock(db: Session, text: str, today: date) -> QueryResult:
    rows = [i for i in db.scalars(select(Ingredient).where(Ingredient.is_active)) if _is_low(i)]
    rows.sort(key=lambda i: i.name.lower())
    if not rows:
        return QueryResult("no_data", "No tienes insumos bajo el mínimo.", _src("inventory", "tu inventario"))
    lines = [_low_line(i) for i in rows[:MAX_LIST]]
    more = f" y {len(rows) - MAX_LIST} más" if len(rows) > MAX_LIST else ""
    return QueryResult(
        "ok",
        f"Tienes {len(rows)} insumos bajo el mínimo: " + "; ".join(lines) + more + ".",
        _src("inventory", "tu inventario"),
        {"count": len(rows)},
    )


def _low_line(i: Ingredient) -> str:
    minimum = human_qty(i.min_stock_qty or Decimal(0), i.base_unit)
    return f"{i.name} ({human_qty(i.stock_qty, i.base_unit)}; mínimo {minimum})"


def _is_low(i: Ingredient) -> bool:
    return i.min_stock_qty is not None and i.stock_qty < i.min_stock_qty


def get_recipe_cost(db: Session, text: str, today: date) -> QueryResult:
    choices = {r.id: r.name for r in db.scalars(select(Recipe).where(Recipe.is_active))}
    found, ask = _resolve("recipe", text, choices, lambda n: f"¿Cuánto me sale {n}?", "producto")
    if found is None:
        return ask  # type: ignore[return-value]
    recipe = recipes.get_recipe(db, found)
    qty = parse_qty(text)
    cost = recipes.compute_cost(db, recipe, qty)
    unit = "unidades" if recipe.yield_unit == BaseUnit.UNIT else BASE_UNIT_LABELS[recipe.yield_unit]
    out = f"Producir {format_decimal(cost.units)} {unit} de {recipe.name} te cuesta {format_clp(cost.total_clp)}"
    if cost.per_unit_clp is not None and recipe.yield_unit == BaseUnit.UNIT:
        out += f" ({format_clp(cost.per_unit_clp)} por unidad)"
    out += ", con IVA y los precios vigentes."
    if not cost.is_complete:
        out += f" Ojo: falta el precio de {', '.join(cost.missing_prices)}, así que el total es parcial."
    return QueryResult(
        "ok",
        out,
        _src("recipe_cost", "tus recetas y los precios vigentes de tus proveedores"),
        {"recipe": recipe.name, "qty": str(cost.units)},
    )


def list_upcoming_orders(db: Session, text: str, today: date) -> QueryResult:
    start, end, label = parse_range(text, today)
    stmt = (
        select(Order)
        .where(
            Order.event_date >= start,
            Order.event_date <= end,
            Order.status.in_([OrderStatus.DRAFT, OrderStatus.CONFIRMED]),
        )
        .order_by(Order.event_date, Order.created_at)
    )
    rows = list(db.scalars(stmt))
    src = _src("orders", "tus pedidos")
    ent = {"from": start.isoformat(), "to": end.isoformat()}
    if not rows:
        return QueryResult("no_data", f"No tienes pedidos para {label}.", src, ent)
    lines = [
        f"{fmt_date(o.event_date)}: {o.customer_name}"  # type: ignore[arg-type]
        + (f", {o.guests} personas" if o.guests else "")
        + f" ({ORDER_STATUS_ES[o.status]})"
        for o in rows[:MAX_LIST]
    ]
    more = f" y {len(rows) - MAX_LIST} más" if len(rows) > MAX_LIST else ""
    return QueryResult("ok", f"Para {label} tienes {len(rows)} pedidos: " + "; ".join(lines) + more + ".", src, ent)


def compare_prices(db: Session, text: str, today: date) -> QueryResult:
    choices = {i.id: i.name for i in db.scalars(select(Ingredient).where(Ingredient.is_active))}
    found, ask = _resolve("ingredient", text, choices, lambda n: f"¿Dónde está más barato {n}?", "insumo")
    if found is None:
        return ask  # type: ignore[return-value]
    cmp = suppliers.compare_prices(db, found)
    src = _src("prices", "los precios vigentes de tus proveedores")
    if not cmp.items:
        return QueryResult(
            "no_data", f"No tengo precios cargados de {cmp.ingredient_name}.", src, {"item": cmp.ingredient_name}
        )
    best = cmp.items[0]
    price = format_clp(Decimal(best.price_per_reference_clp))
    out = (
        f"Lo más barato de {cmp.ingredient_name} es {best.supplier_name}: {price} por {best.reference_unit} con IVA "
        f"(presentación {best.package_label}, precio del {best.price_date:%d/%m/%Y})."
    )
    if len(cmp.items) > 1:
        nxt = cmp.items[1]
        nxt_price = format_clp(Decimal(nxt.price_per_reference_clp))
        out += f" Le sigue {nxt.supplier_name} con {nxt_price} por {nxt.reference_unit}."
    return QueryResult("ok", out, src, {"item": cmp.ingredient_name})


# Qué dato del proveedor se pide. Sin ninguno ("¿y Molino Sur?") se responde despacho y contacto completos.
SUPPLIER_FIELDS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b(correo|mail|email|e-mail)s?\b"),
    "phone": re.compile(r"\b(telefono|fono|celular|numero|whatsapp|wsp|llamar)s?\b"),
    "website": re.compile(r"\b(web|pagina|sitio|link|enlace)s?\b"),
    "delivery": re.compile(r"\b(despach\w*|repart\w*|entreg\w*|llega\w*|dias?)\b"),
}
CONTACT = re.compile(r"\b(contacto|contactar|contactarlo|contactarla|ubicar)\b")
FIELD_ES = {"email": "el correo", "phone": "el teléfono", "website": "la página web"}


def _not_registered(items: list[str], name: str) -> str:
    if len(items) == 1:
        word = "registrada" if items[0].startswith("la ") else "registrado"
        return f"No tengo {word} {items[0]} de {name}."
    return f"No tengo registrados {', '.join(items[:-1])} ni {items[-1]} de {name}."


def _supplier_fields(text: str) -> list[str]:
    q = normalize_question(text)
    asked = [f for f, rx in SUPPLIER_FIELDS.items() if rx.search(q)]
    if CONTACT.search(q):
        asked += [f for f in ("phone", "email", "website") if f not in asked]
    return asked or ["delivery", "phone", "email", "website"]


def get_supplier(db: Session, text: str, today: date) -> QueryResult:
    choices = {s.id: s.name for s in db.scalars(select(Supplier).where(Supplier.is_active))}
    found, ask = _resolve("supplier", text, choices, lambda n: f"¿Qué días despacha {n}?", "proveedor")
    if found is None:
        return ask  # type: ignore[return-value]
    sup = suppliers.get_supplier(db, found)
    asked = _supplier_fields(text)
    explicit = asked != ["delivery", "phone", "email", "website"]
    values = {"phone": sup.phone, "email": sup.email, "website": sup.website}
    parts: list[str] = []
    if "delivery" in asked:
        days = [WEEKDAYS_LONG[d - 1] for d in sorted(sup.delivery_days or []) if 1 <= d <= 7]
        parts.append(
            f"{sup.name} despacha {_join(days)}."
            if days
            else f"No tengo registrados los días de despacho de {sup.name}."
        )
    labels = {"phone": "Teléfono", "email": "Correo", "website": "Página web"}
    missing = [f for f in ("phone", "email", "website") if f in asked and not values[f]]
    for f in ("phone", "email", "website"):
        if f in asked and values[f]:
            parts.append(
                f"{labels[f]}: {values[f]}." if parts or not explicit else f"{labels[f]} de {sup.name}: {values[f]}."
            )
    if explicit and missing:  # se pidió ese dato y no está: se dice, no se cambia por otro
        parts.append(_not_registered([FIELD_ES[f] for f in missing], sup.name))
        if not any(values[f] for f in asked if f in values) and "delivery" not in asked:
            have = [f"{labels[f].lower()} {values[f]}" for f in ("phone", "email", "website") if values[f]]
            if have:
                parts.append(f"Sí tengo su {_join(have)}.")
    return QueryResult(
        "ok", " ".join(parts), _src("suppliers", "tus proveedores"), {"supplier": sup.name, "asked": asked}
    )


# --------------------------------------------------------------------------- un pedido en particular


def _when(o: Order) -> str:
    return fmt_date(o.event_date) if o.event_date else "sin fecha"


def _order_label(o: Order) -> str:
    return f"{o.customer_name} ({_when(o)})"


def _find_order(
    db: Session, text: str, today: date, ask: Callable[[Order], str]
) -> tuple[Order | None, QueryResult | None]:
    """Pedido próximo del que habla la pregunta: por nombre del cliente, por fecha o el único que hay.
    Si no queda claro, ofrece opciones (nunca adivina)."""
    stmt = (
        select(Order)
        .where(Order.status.in_(ACTIVE_ORDERS), or_(Order.event_date.is_(None), Order.event_date >= today))
        .order_by(Order.event_date.nulls_last(), Order.created_at)
        .limit(50)
    )
    orders = list(db.scalars(stmt))
    src = _src("orders", "tus pedidos")
    if not orders:
        return None, QueryResult("no_data", "No tienes pedidos próximos.", src)

    def choose(cands: list[Order], msg: str) -> QueryResult:
        opts = [{"label": _order_label(o), "question": ask(o)} for o in cands[:4]]
        return QueryResult("ambiguous", msg, src, options=opts)

    by_name = find_entity(text, {o.id: o.customer_name for o in orders})
    if by_name.match:
        return next(o for o in orders if o.id == by_name.match.id), None
    named = [o for o in orders if o.id in {c.id for c in by_name.suggestions}]
    day = parse_event_date(text, today)
    if day is not None:
        same = [o for o in (named or orders) if o.event_date == day]
        if len(same) == 1:
            return same[0], None
        if not same:
            return None, QueryResult("no_data", f"No tienes pedidos para el {fmt_date(day)}.", src)
        return None, choose(same, f"El {fmt_date(day)} tienes {len(same)} pedidos. ¿Cuál?")
    if named:
        return None, choose(named, "¿De cuál pedido me hablas?")
    if len(orders) == 1:
        return orders[0], None
    return None, choose(orders, "¿De cuál pedido me hablas? Estos son los próximos.")


def _line_name(db: Session, recipe_id: uuid.UUID | None, requested: str) -> str:
    r = db.get(Recipe, recipe_id) if recipe_id else None
    return r.name if r else requested


def get_order(db: Session, text: str, today: date) -> QueryResult:
    order, ask = _find_order(db, text, today, lambda o: f"¿Qué lleva el pedido de {o.customer_name} del {_when(o)}?")
    if order is None:
        return ask  # type: ignore[return-value]
    parts = []
    for line in order.lines:
        singular, plural = ORDER_UNIT_LABELS[line.unit]
        unit = singular if line.qty == 1 else plural
        parts.append(f"{format_decimal(line.qty)} {unit} de {_line_name(db, line.recipe_id, line.requested_name)}")
    extra = f", {order.guests} personas" if order.guests else ""
    head = f"El pedido de {order.customer_name} para el {_when(order)} ({ORDER_STATUS_ES[order.status]}{extra})"
    body = f" lleva: {'; '.join(parts)}." if parts else " todavía no tiene productos."
    ent = {"order": str(order.id), "customer": order.customer_name}
    return QueryResult("ok", head + body, _src("orders", "tus pedidos"), ent)


def check_order_stock(db: Session, text: str, today: date) -> QueryResult:
    order, ask = _find_order(
        db, text, today, lambda o: f"¿Me alcanza para el pedido de {o.customer_name} del {_when(o)}?"
    )
    if order is None:
        return ask  # type: ignore[return-value]
    src = _src("orders", "tu pedido, tus recetas y tu inventario de hoy")
    ent = {"order": str(order.id), "customer": order.customer_name}
    who = f"el pedido de {order.customer_name} ({_when(order)})"
    try:
        result = quotes.stock_check(db, order)
    except ProblemError as exc:
        return QueryResult("no_data", f"No puedo revisar {who}: {exc.detail or exc.title}.", src, ent)
    except QuoteCalculationError as exc:
        return QueryResult("no_data", f"No puedo revisar {who}: {exc}.", src, ent)
    rows = result.ingredients
    only = find_entity(text, {r.ingredient.id: r.ingredient.name for r in rows})
    if only.match:  # "¿me alcanza la harina para...?": solo ese insumo
        rows = [r for r in rows if r.ingredient.id == only.match.id]
    short = [r for r in rows if r.to_buy_qty > 0]
    note = " Ojo: cuenta solo este pedido, no los otros que usen el mismo stock."
    if not short:
        what = rows[0].ingredient.name if only.match and rows else "lo que tienes en stock"
        return QueryResult("ok", f"Para {who} te alcanza con {what}." + note, src, ent)
    lines = [
        f"{r.ingredient.name}: faltan {human_qty(r.to_buy_qty, r.ingredient.base_unit)} "
        f"(necesitas {human_qty(r.required_qty, r.ingredient.base_unit)} y tienes "
        f"{human_qty(r.stock_used_qty, r.ingredient.base_unit)})"
        for r in short[:MAX_LIST]
    ]
    more = f" y {len(short) - MAX_LIST} más" if len(short) > MAX_LIST else ""
    text_out = f"Para {who} no te alcanza. " + "; ".join(lines) + more + "." + note
    return QueryResult("ok", text_out, src, ent)


# --------------------------------------------------------------------------- producción (F2)


def get_production(db: Session, text: str, today: date) -> QueryResult:
    start, end, label = parse_past_range(text, today)
    lo = datetime.combine(start, time.min, TZ)
    hi = datetime.combine(end + timedelta(days=1), time.min, TZ)
    rows = db.execute(
        select(ProductionRecord.recipe_id, func.sum(ProductionRecord.confirmed_qty), func.count())
        .where(ProductionRecord.created_at >= lo, ProductionRecord.created_at < hi)
        .group_by(ProductionRecord.recipe_id)
    ).all()
    src = _src("production", "tus registros de producción")
    ent = {"from": start.isoformat(), "to": end.isoformat()}
    made = {r.id: r for r in db.scalars(select(Recipe).where(Recipe.id.in_([row[0] for row in rows])))}
    only = find_entity(text, {rid: r.name for rid, r in made.items()})
    if only.match:
        rows = [row for row in rows if row[0] == only.match.id]
    if not rows:
        return QueryResult("no_data", f"No tienes producción registrada {_period(label)}.", src, ent)
    rows = sorted(rows, key=lambda row: -int(row[1]))
    parts = []
    for rid, qty, _n in rows[:MAX_LIST]:
        r = made[rid]
        unit = "unidades" if r.yield_unit == BaseUnit.UNIT else BASE_UNIT_LABELS[r.yield_unit]
        parts.append(f"{format_decimal(Decimal(qty))} {unit} de {r.name}")
    records = sum(int(row[2]) for row in rows)
    head = _period(label)
    return QueryResult(
        "ok", f"{head[0].upper()}{head[1:]} registraste " + "; ".join(parts) + f" ({records} registros).", src, ent
    )


def _period(label: str) -> str:
    return label if label in ("hoy", "ayer") else f"en {label}"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


QUERIES: dict[str, Callable[[Session, str, date], QueryResult]] = {
    "get_stock": get_stock,
    "list_low_stock": list_low_stock,
    "get_recipe_cost": get_recipe_cost,
    "list_upcoming_orders": list_upcoming_orders,
    "compare_prices": compare_prices,
    "get_supplier": get_supplier,
    "get_order": get_order,
    "check_order_stock": check_order_stock,
    "get_production": get_production,
}

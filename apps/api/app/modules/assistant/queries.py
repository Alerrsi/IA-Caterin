"""Consultas tipadas de solo lectura del asistente (AGENTS.md sección 4). Filtran por pyme por la sesión de tenant.

Cada una resuelve entidades en código y devuelve la respuesta de nivel 0 ya redactada con plantilla: los números
salen de los servicios de T04/T05, nunca de un LLM. Si no hay dato, lo dice.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import format_clp
from app.core.units import BASE_UNIT_LABELS, format_decimal, human_qty
from app.db.enums import BaseUnit, OrderStatus
from app.db.models import Ingredient, Order, Recipe, Supplier
from app.modules.assistant.entities import find_entity
from app.modules.assistant.parsing import WEEKDAYS_LONG, fmt_date, parse_qty, parse_range
from app.modules.recipes import service as recipes
from app.modules.suppliers import service as suppliers

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
    found, ask = _resolve("ingredient", text, choices, lambda n: f"¿Cuánto {n} me queda?", "insumo")
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


def get_supplier(db: Session, text: str, today: date) -> QueryResult:
    choices = {s.id: s.name for s in db.scalars(select(Supplier).where(Supplier.is_active))}
    found, ask = _resolve("supplier", text, choices, lambda n: f"¿Qué días despacha {n}?", "proveedor")
    if found is None:
        return ask  # type: ignore[return-value]
    sup = suppliers.get_supplier(db, found)
    days = [WEEKDAYS_LONG[d - 1] for d in sorted(sup.delivery_days or []) if 1 <= d <= 7]
    parts = [
        f"{sup.name} despacha {_join(days)}." if days else f"No tengo registrados los días de despacho de {sup.name}."
    ]
    if sup.phone:
        parts.append(f"Teléfono: {sup.phone}.")
    if sup.email:
        parts.append(f"Correo: {sup.email}.")
    return QueryResult("ok", " ".join(parts), _src("suppliers", "tus proveedores"), {"supplier": sup.name})


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


QUERIES: dict[str, Callable[[Session, str, date], QueryResult]] = {
    "get_stock": get_stock,
    "list_low_stock": list_low_stock,
    "get_recipe_cost": get_recipe_cost,
    "list_upcoming_orders": list_upcoming_orders,
    "compare_prices": compare_prices,
    "get_supplier": get_supplier,
}

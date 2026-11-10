"""Texto de las fichas del negocio (ADR-006). Lo arma código desde las tablas: el LLM nunca escribe una ficha.

Una ficha por insumo, receta y proveedor activos, y por pedido en borrador o confirmado. Las cifras son las
guardadas (stock, precios, cantidades), con el formato de la app; no hay cálculos nuevos aquí. Las fichas de
pedidos llevan el nombre del cliente, pero no su contacto (datos personales mínimos, SECURITY.md).
"""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.money import format_clp
from app.core.units import BASE_UNIT_LABELS, format_decimal, human_qty
from app.db.enums import DataDomain, OrderStatus
from app.db.models import Ingredient, Order, Recipe, Supplier
from app.modules.assistant.parsing import WEEKDAYS_LONG
from app.modules.quotes.calculator import ORDER_UNIT_LABELS
from app.modules.suppliers import service as suppliers

KINDS = ("ingredient", "recipe", "supplier", "order")
# Qué dominios de `data_version` cambian el texto de cada tipo de ficha.
DEPENDS_ON: dict[str, tuple[DataDomain, ...]] = {
    "ingredient": (DataDomain.INVENTORY, DataDomain.SUPPLIERS),
    "recipe": (DataDomain.RECIPES, DataDomain.INVENTORY),
    "supplier": (DataDomain.SUPPLIERS, DataDomain.INVENTORY),
    "order": (DataDomain.ORDERS, DataDomain.RECIPES),
}
SOURCE = {"ingredient": "tu inventario", "recipe": "tus recetas", "supplier": "tus proveedores", "order": "tus pedidos"}
ORDER_STATUS = {OrderStatus.DRAFT: "borrador", OrderStatus.CONFIRMED: "confirmado"}


@dataclass(frozen=True)
class CardData:
    kind: str
    entity_id: uuid.UUID
    title: str
    text: str

    @property
    def text_hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


def _date(d: object) -> str:
    return f"{d:%d/%m/%Y}"


def ingredient_cards(db: Session) -> list[CardData]:
    rows = list(db.scalars(select(Ingredient).where(Ingredient.is_active).order_by(Ingredient.name)))
    offers = suppliers.current_options(db, [i.id for i in rows])
    out = []
    for i in rows:
        parts = [f"Insumo: {i.name}."]
        if i.category:
            parts.append(f"Categoría: {i.category}.")
        stock = f"Stock: {human_qty(i.stock_qty, i.base_unit)}"
        if i.min_stock_qty is not None:
            stock += f" (mínimo {human_qty(i.min_stock_qty, i.base_unit)})"
            if i.stock_qty < i.min_stock_qty:
                stock += ", bajo el mínimo"
        parts.append(stock + ".")
        if i.waste_pct:
            parts.append(f"Merma: {format_decimal(i.waste_pct)} %.")
        opts = sorted(offers.get(i.id, []), key=lambda o: o.supplier_name)
        if opts:
            parts.append(
                "Lo vende: "
                + "; ".join(
                    f"{o.supplier_name}, {o.package_label} a {format_clp(o.price_clp)}"
                    f"{'' if o.includes_vat else ' + IVA'} (precio del {_date(o.price_date)})"
                    for o in opts
                )
                + "."
            )
        else:
            parts.append("Sin precios de proveedores cargados.")
        out.append(CardData("ingredient", i.id, i.name, " ".join(parts)))
    return out


def recipe_cards(db: Session) -> list[CardData]:
    rows = list(
        db.scalars(select(Recipe).where(Recipe.is_active).options(selectinload(Recipe.lines)).order_by(Recipe.name))
    )
    ings = {i.id: i for i in db.scalars(select(Ingredient))}
    out = []
    for r in rows:
        parts = [f"Receta: {r.name}.", f"Rinde {format_decimal(r.yield_qty)} {BASE_UNIT_LABELS[r.yield_unit]}."]
        lines = [
            f"{human_qty(line.qty, ings[line.ingredient_id].base_unit)} de {ings[line.ingredient_id].name}"
            for line in r.lines
            if line.ingredient_id in ings
        ]
        if lines:
            parts.append("Ingredientes: " + "; ".join(lines) + ".")
        parts.append("Producto final." if r.is_final_product else "Preparación intermedia.")
        if r.notes:
            parts.append(f"Notas: {r.notes.strip()}")
        out.append(CardData("recipe", r.id, r.name, " ".join(parts)))
    return out


def supplier_cards(db: Session) -> list[CardData]:
    rows = list(db.scalars(select(Supplier).where(Supplier.is_active).order_by(Supplier.name)))
    ings = {i.id: i.name for i in db.scalars(select(Ingredient).where(Ingredient.is_active))}
    offers = suppliers.current_options(db, list(ings))
    by_supplier: dict[uuid.UUID, list[str]] = {}
    for ing_id, opts in offers.items():
        for o in opts:
            by_supplier.setdefault(o.supplier_id, []).append(
                f"{ings[ing_id]} ({o.package_label}, {format_clp(o.price_clp)}{'' if o.includes_vat else ' + IVA'})"
            )
    out = []
    for s in rows:
        parts = [f"Proveedor: {s.name}."]
        days = [WEEKDAYS_LONG[d - 1] for d in sorted(s.delivery_days or []) if 1 <= d <= 7]
        if days:
            parts.append("Despacha: " + ", ".join(days) + ".")
        for label, value in (("Teléfono", s.phone), ("Correo", s.email), ("Sitio web", s.website)):
            if value:
                parts.append(f"{label}: {value}.")
        sold = sorted(by_supplier.get(s.id, []))
        parts.append("Vende: " + "; ".join(sold) + "." if sold else "Sin productos con precio cargado.")
        if s.notes:
            parts.append(f"Notas: {s.notes.strip()}")
        out.append(CardData("supplier", s.id, s.name, " ".join(parts)))
    return out


def order_cards(db: Session) -> list[CardData]:
    rows = list(
        db.scalars(
            select(Order)
            .where(Order.status.in_(tuple(ORDER_STATUS)))
            .options(selectinload(Order.lines))
            .order_by(Order.event_date)
        )
    )
    recipes = {r.id: r.name for r in db.scalars(select(Recipe))}
    out = []
    for o in rows:
        when = f"para el {WEEKDAYS_LONG[o.event_date.weekday()]} {_date(o.event_date)}" if o.event_date else "sin fecha"
        parts = [f"Pedido de {o.customer_name} {when}, estado {ORDER_STATUS[o.status]}."]
        if o.guests:
            parts.append(f"Invitados: {o.guests}.")
        items = []
        for line in sorted(o.lines, key=lambda x: x.position):
            singular, plural = ORDER_UNIT_LABELS[line.unit]
            unit = singular if line.qty == Decimal(1) else plural
            name = recipes.get(line.recipe_id, line.requested_name) if line.recipe_id else line.requested_name
            items.append(f"{format_decimal(line.qty)} {unit} de {name}")
        if items:
            parts.append("Productos: " + "; ".join(items) + ".")
        if o.notes:
            parts.append(f"Notas: {o.notes.strip()}")
        out.append(
            CardData(
                "order",
                o.id,
                f"{o.customer_name} ({_date(o.event_date) if o.event_date else 'sin fecha'})",
                " ".join(parts),
            )
        )
    return out


BUILDERS: dict[str, Callable[[Session], list[CardData]]] = {
    "ingredient": ingredient_cards,
    "recipe": recipe_cards,
    "supplier": supplier_cards,
    "order": order_cards,
}

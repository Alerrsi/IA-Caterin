"""Existencias de productos terminados (T18, ADR-011).

Mismo patrón que los insumos (ADR-004): el libro `product_movement` solo crece y `recipe.stock_qty` es su saldo,
actualizado con una suma atómica en la base. Un producto terminado es una receta final (`is_final_product`), y su
cantidad está en la unidad de rendimiento de la receta (unidad, g o ml).
"""

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.data_version import bump
from app.core.errors import not_found
from app.core.http import decode_cursor, encode_cursor
from app.core.units import quantize_qty
from app.db.enums import BaseUnit, DataDomain, OrderStatus, OrderUnit, ProductMovementReason
from app.db.models import Order, ProductMovement, Recipe
from app.modules.inventory.schemas import ProductMovementCreate

ORDER_REF = "order"
PRODUCTION_REF = "production"

# Cuánto vale una unidad del pedido en la unidad de rendimiento de la receta. Lo que no calza no se descuenta.
_ORDER_FACTOR: dict[BaseUnit, dict[OrderUnit, Decimal]] = {
    BaseUnit.UNIT: {OrderUnit.UNIT: Decimal(1), OrderUnit.PORTION: Decimal(1), OrderUnit.DOZEN: Decimal(12)},
    BaseUnit.GRAM: {OrderUnit.GRAM: Decimal(1), OrderUnit.KILOGRAM: Decimal(1000)},
    BaseUnit.MILLILITER: {OrderUnit.MILLILITER: Decimal(1), OrderUnit.LITER: Decimal(1000)},
}


def get_product(db: Session, recipe_id: uuid.UUID) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or not recipe.is_final_product:
        raise not_found("product_not_found", "No encontramos ese producto")
    return recipe


def apply_product_movement(
    db: Session,
    recipe: Recipe,
    delta: Decimal,
    reason: ProductMovementReason,
    note: str | None = None,
    reference: tuple[str, uuid.UUID] | None = None,
    client_op_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
) -> ProductMovement:
    """Agrega el movimiento y suma el saldo en la base (dos movimientos simultáneos no se pisan). No hace commit."""
    movement = ProductMovement(
        recipe_id=recipe.id, delta_qty=quantize_qty(delta), reason=reason, note=note, client_op_id=client_op_id
    )
    if reference is not None:
        movement.reference_type, movement.reference_id = reference
    if occurred_at is not None:
        movement.occurred_at = occurred_at
    db.add(movement)
    db.execute(update(Recipe).where(Recipe.id == recipe.id).values(stock_qty=Recipe.stock_qty + movement.delta_qty))
    db.flush()
    db.refresh(recipe)
    return movement


def list_product_stock(db: Session) -> list[Recipe]:
    stmt = (
        select(Recipe)
        .where(Recipe.is_final_product.is_(True), Recipe.is_active.is_(True))
        .order_by(func.lower(Recipe.name))
    )
    return list(db.scalars(stmt))


def list_product_movements(
    db: Session, recipe_id: uuid.UUID, limit: int, cursor: str | None
) -> tuple[list[ProductMovement], str | None]:
    get_product(db, recipe_id)
    stmt = select(ProductMovement).where(ProductMovement.recipe_id == recipe_id)
    after = decode_cursor(cursor)
    if after:
        stmt = stmt.where(
            tuple_(ProductMovement.created_at, ProductMovement.id)
            < tuple_(datetime.fromisoformat(after[0]), uuid.UUID(after[1]))
        )
    rows = list(
        db.scalars(stmt.order_by(ProductMovement.created_at.desc(), ProductMovement.id.desc()).limit(limit + 1))
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor([rows[-1].created_at.isoformat(), str(rows[-1].id)]) if has_more else None
    return rows, next_cursor


def _by_op(db: Session, client_op_id: uuid.UUID) -> ProductMovement | None:
    return db.scalar(select(ProductMovement).where(ProductMovement.client_op_id == client_op_id))


def record_product_movement(
    db: Session, data: ProductMovementCreate, client_op_id: uuid.UUID | None
) -> tuple[ProductMovement, Recipe, bool]:
    """Ajuste manual o merma. Con la misma clave de idempotencia devuelve el original (replayed=True)."""
    if client_op_id is not None and (existing := _by_op(db, client_op_id)) is not None:
        return existing, get_product(db, existing.recipe_id), True
    recipe = get_product(db, data.recipe_id)
    movement = apply_product_movement(
        db,
        recipe,
        data.delta_qty,
        ProductMovementReason(data.reason),
        note=data.note,
        client_op_id=client_op_id,
        occurred_at=data.occurred_at,
    )
    bump(db, DataDomain.PRODUCTION)
    try:
        db.commit()
    except IntegrityError:  # otra solicitud con la misma clave ganó la carrera
        db.rollback()
        existing = _by_op(db, client_op_id) if client_op_id else None
        if existing is None:  # pragma: no cover
            raise
        return existing, get_product(db, existing.recipe_id), True
    db.refresh(recipe)
    return movement, recipe, False


# --------------------------------------------------------------------------- entregas de pedidos


def delivery_units(lines: list[tuple[uuid.UUID, Decimal, OrderUnit, BaseUnit]]) -> dict[uuid.UUID, Decimal]:
    """Unidades de rendimiento por receta que se llevan las líneas de un pedido. Función pura.

    `lines`: (recipe_id, cantidad, unidad del pedido, unidad de rendimiento de la receta). Una línea cuya unidad no
    calza con la receta (p. ej. kg de una receta que rinde unidades) no se descuenta.
    """
    out: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for recipe_id, qty, unit, yield_unit in lines:
        factor = _ORDER_FACTOR.get(yield_unit, {}).get(unit)
        if factor is not None:
            out[recipe_id] += qty * factor
    return {rid: quantize_qty(q) for rid, q in out.items() if q > 0}


def sync_order_delivery(db: Session, order: Order) -> bool:
    """Deja el libro de productos de acuerdo con el pedido: si está entregado, descontado una vez; si no, nada.

    Compara lo que debería estar descontado con lo ya aplicado (referencia ('order', id)) y aplica solo la diferencia,
    así cambiar el estado o las líneas de un pedido entregado nunca descuenta dos veces. No hace commit.
    Devuelve True si movió algo.
    """
    desired: dict[uuid.UUID, Decimal] = {}
    if order.status == OrderStatus.DELIVERED:
        recipe_ids = [line.recipe_id for line in order.lines if line.recipe_id is not None]
        recipes = {r.id: r for r in db.scalars(select(Recipe).where(Recipe.id.in_(recipe_ids)))} if recipe_ids else {}
        desired = delivery_units(
            [
                (line.recipe_id, line.qty, line.unit, recipes[line.recipe_id].yield_unit)
                for line in order.lines
                if line.recipe_id in recipes and recipes[line.recipe_id].is_final_product
            ]
        )
    applied = dict(
        db.execute(
            select(ProductMovement.recipe_id, func.sum(ProductMovement.delta_qty))
            .where(ProductMovement.reference_type == ORDER_REF, ProductMovement.reference_id == order.id)
            .group_by(ProductMovement.recipe_id)
        ).all()
    )
    moved = False
    for recipe_id in sorted(set(desired) | set(applied), key=str):
        diff = -desired.get(recipe_id, Decimal(0)) - Decimal(applied.get(recipe_id) or 0)
        if diff == 0:
            continue
        recipe = db.get(Recipe, recipe_id)
        if recipe is None:  # pragma: no cover - la FK lo impide
            continue
        reason = ProductMovementReason.DELIVERY if diff < 0 else ProductMovementReason.VOID
        note = "Pedido entregado" if diff < 0 else "El pedido dejó de estar entregado"
        apply_product_movement(db, recipe, diff, reason, note=note, reference=(ORDER_REF, order.id))
        moved = True
    if moved:
        bump(db, DataDomain.PRODUCTION)
    return moved

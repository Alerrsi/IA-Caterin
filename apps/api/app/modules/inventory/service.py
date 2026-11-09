"""Insumos y stock. El stock es un libro de movimientos con saldo cacheado (ADR-004)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.http import Page, decode_cursor, encode_cursor
from app.core.units import UnitConversionError, quantize_qty, to_base
from app.db.enums import DataDomain, MovementReason
from app.db.models import Ingredient, StockMovement
from app.modules.inventory.schemas import IngredientCreate, IngredientOut, IngredientUpdate, MovementCreate

_DUPLICATE = ProblemError(409, "ingredient_exists", "Ya tienes un insumo con ese nombre")


def convert_qty(qty: Decimal, unit: str | None, ing: Ingredient) -> Decimal:
    """Convierte a la unidad base del insumo; sin unidad, se asume que ya viene en unidad base."""
    if unit is None or unit.strip() == "":
        return qty
    try:
        return to_base(qty, unit, ing.base_unit, ing.density_g_per_ml)
    except UnitConversionError as exc:
        raise ProblemError(422, "unit_conversion", "No se puede usar esa unidad con este insumo", str(exc)) from exc


def _name_key(name: str) -> str:
    return " ".join(name.split())


def list_ingredients(
    db: Session,
    q: str | None,
    limit: int,
    cursor: str | None,
    updated_since: datetime | None = None,
    include_inactive: bool = False,
    low_only: bool = False,
) -> Page[IngredientOut]:
    stmt = select(Ingredient)
    if not include_inactive:
        stmt = stmt.where(Ingredient.is_active)
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{q.strip()}%"))
    if updated_since:
        stmt = stmt.where(Ingredient.updated_at > updated_since)
    if low_only:
        stmt = stmt.where(Ingredient.min_stock_qty.is_not(None), Ingredient.stock_qty < Ingredient.min_stock_qty)
    key = (func.lower(Ingredient.name), Ingredient.id)
    after = decode_cursor(cursor)
    if after:
        stmt = stmt.where(tuple_(*key) > tuple_(after[0], uuid.UUID(after[1])))
    rows = list(db.scalars(stmt.order_by(*key).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor([rows[-1].name.lower(), str(rows[-1].id)]) if has_more else None
    return Page[IngredientOut](items=[IngredientOut.model_validate(r) for r in rows], next_cursor=next_cursor)


def get_ingredient(db: Session, ingredient_id: uuid.UUID) -> Ingredient:
    ing = db.get(Ingredient, ingredient_id)
    if ing is None:
        raise not_found("ingredient_not_found", "No encontramos ese insumo")
    return ing


def create_ingredient(db: Session, data: IngredientCreate, import_batch_id: uuid.UUID | None = None) -> Ingredient:
    ing = Ingredient(
        name=_name_key(data.name),
        base_unit=data.base_unit,
        stock_qty=Decimal(0),
        min_stock_qty=data.min_stock_qty,
        waste_pct=data.waste_pct,
        density_g_per_ml=data.density_g_per_ml,
        category=data.category,
        import_batch_id=import_batch_id,
    )
    db.add(ing)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _DUPLICATE from exc
    if data.initial_stock > 0:
        reason = MovementReason.IMPORT if import_batch_id else MovementReason.ADJUSTMENT
        _apply_movement(db, ing, data.initial_stock, reason, "Stock inicial", None, None)
    bump(db, DataDomain.INVENTORY)
    return ing


def update_ingredient(db: Session, ingredient_id: uuid.UUID, data: IngredientUpdate) -> Ingredient:
    ing = get_ingredient(db, ingredient_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name"):
        ing.name = _name_key(changes["name"])
    for field in ("min_stock_qty", "waste_pct", "density_g_per_ml", "category"):
        if field in changes:
            setattr(ing, field, changes[field])
    if changes.get("is_active") is not None:
        ing.is_active = changes["is_active"]
    try:
        bump(db, DataDomain.INVENTORY, DataDomain.RECIPES)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _DUPLICATE from exc
    db.refresh(ing)
    return ing


def _apply_movement(
    db: Session,
    ing: Ingredient,
    delta: Decimal,
    reason: MovementReason,
    note: str | None,
    occurred_at: datetime | None,
    client_op_id: uuid.UUID | None,
) -> StockMovement:
    movement = StockMovement(ingredient_id=ing.id, delta_qty=delta, reason=reason, note=note, client_op_id=client_op_id)
    if occurred_at:
        movement.occurred_at = occurred_at
    db.add(movement)
    # Suma atómica en la base: dos movimientos simultáneos no se pisan.
    db.execute(update(Ingredient).where(Ingredient.id == ing.id).values(stock_qty=Ingredient.stock_qty + delta))
    db.flush()
    db.refresh(ing)
    return movement


def record_movement(
    db: Session, data: MovementCreate, client_op_id: uuid.UUID | None
) -> tuple[StockMovement, Ingredient, bool]:
    """Registra un movimiento. Con la misma clave de idempotencia devuelve el original (replayed=True)."""
    if client_op_id is not None:
        existing = db.scalar(select(StockMovement).where(StockMovement.client_op_id == client_op_id))
        if existing is not None:
            return existing, get_ingredient(db, existing.ingredient_id), True
    ing = get_ingredient(db, data.ingredient_id)
    if not ing.is_active:
        raise ProblemError(409, "ingredient_inactive", "Ese insumo está desactivado")
    delta = quantize_qty(convert_qty(data.delta_qty, data.unit, ing))
    movement = _apply_movement(db, ing, delta, data.reason, data.note, data.occurred_at, client_op_id)
    bump(db, DataDomain.INVENTORY)
    try:
        db.commit()
    except IntegrityError:  # otra solicitud con la misma clave ganó la carrera
        db.rollback()
        existing = db.scalar(select(StockMovement).where(StockMovement.client_op_id == client_op_id))
        if existing is None:  # pragma: no cover
            raise
        return existing, get_ingredient(db, existing.ingredient_id), True
    db.refresh(ing)
    return movement, ing, False


def list_movements(
    db: Session, ingredient_id: uuid.UUID, limit: int, cursor: str | None
) -> tuple[list[StockMovement], str | None]:
    get_ingredient(db, ingredient_id)
    stmt = select(StockMovement).where(StockMovement.ingredient_id == ingredient_id)
    after = decode_cursor(cursor)
    if after:
        stmt = stmt.where(
            tuple_(StockMovement.created_at, StockMovement.id)
            < tuple_(datetime.fromisoformat(after[0]), uuid.UUID(after[1]))
        )
    rows = list(db.scalars(stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor([rows[-1].created_at.isoformat(), str(rows[-1].id)]) if has_more else None
    return rows, next_cursor


# --- lecturas que también usa el asistente (T07) -----------------------------------------------


def list_low_stock(db: Session) -> list[Ingredient]:
    stmt = (
        select(Ingredient)
        .where(
            Ingredient.is_active, Ingredient.min_stock_qty.is_not(None), Ingredient.stock_qty < Ingredient.min_stock_qty
        )
        .order_by(func.lower(Ingredient.name))
    )
    return list(db.scalars(stmt))

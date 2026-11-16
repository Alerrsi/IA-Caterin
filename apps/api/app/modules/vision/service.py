"""Conteo por foto (F2) y confirmación de producción con efecto en el inventario (T18, ADR-011)."""

import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.http import decode_cursor, encode_cursor
from app.db.enums import DataDomain, MovementReason, ProductMovementReason
from app.db.models import Ingredient, ProductionRecord, ProductMovement, Pyme, Recipe, StockMovement
from app.modules.inventory.service import apply_product_movement, apply_system_movement
from app.modules.recipes.costing import ConsumptionInput, production_consumption
from app.modules.vision.detector import Detection
from app.modules.vision.schemas import (
    ConsumedOut,
    CountLine,
    ProductionCreate,
    ProductionOut,
    ProductionPreviewIn,
    ProductionPreviewOut,
)

PRODUCTION_REF = "production"
VOID_NOTE = "Anulación de la producción"


def count_by_class(db: Session, detections: list[Detection]) -> list[CountLine]:
    """Cuenta por clase y la une con la receta (producto final) que declara esa `vision_class`."""
    counts = Counter(d.vision_class for d in detections)
    recipes = {
        r.vision_class: r
        for r in db.scalars(select(Recipe).where(Recipe.vision_class.in_(counts), Recipe.is_active.is_(True)))
    }
    return [
        CountLine(
            vision_class=cls,
            count=n,
            recipe_id=recipes[cls].id if cls in recipes else None,
            recipe_name=recipes[cls].name if cls in recipes else None,
        )
        for cls, n in counts.most_common()
    ]


def _by_op(db: Session, client_op_id: uuid.UUID) -> ProductionRecord | None:
    return db.scalar(select(ProductionRecord).where(ProductionRecord.client_op_id == client_op_id))


def _final_recipe(db: Session, recipe_id: uuid.UUID) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or not recipe.is_final_product:
        raise not_found("recipe_not_found", "No encontramos ese producto")
    return recipe


def _pyme(db: Session) -> Pyme:
    pyme = db.get(Pyme, db.info["pyme_id"])
    if pyme is None:  # pragma: no cover - la sesión siempre es de una pyme existente
        raise not_found("pyme_not_found", "No encontramos tu pyme")
    return pyme


def _consumption(db: Session, recipe: Recipe, units: int, pyme: Pyme) -> list[tuple[Ingredient, Decimal]]:
    """Insumos que usa producir `units` de la receta (mismo cálculo que la cotización). Solo lectura."""
    ingredients = {
        i.id: i
        for i in db.scalars(select(Ingredient).where(Ingredient.id.in_([line.ingredient_id for line in recipe.lines])))
    }
    inputs = [
        ConsumptionInput(line.ingredient_id, line.qty, line.waste_pct, ingredients[line.ingredient_id].waste_pct)
        for line in recipe.lines
        if line.ingredient_id in ingredients
    ]
    used = production_consumption(inputs, recipe.yield_qty, Decimal(units), pyme.default_waste_pct)
    return [(ingredients[iid], qty) for iid, qty in used]


def _consumed_out(ing: Ingredient, qty: Decimal, stock_after: Decimal) -> ConsumedOut:
    return ConsumedOut(
        ingredient_id=ing.id,
        name=ing.name,
        base_unit=ing.base_unit.value,
        qty=qty,
        stock_qty=stock_after,
        went_negative=stock_after < 0,
    )


def preview_production(db: Session, data: ProductionPreviewIn) -> ProductionPreviewOut:
    """Lo que sumaría y descontaría confirmar esta producción, sin escribir nada."""
    recipe = _final_recipe(db, data.recipe_id)
    pyme = _pyme(db)
    consume = pyme.production_consumes_ingredients if data.consume_ingredients is None else data.consume_ingredients
    used = _consumption(db, recipe, data.confirmed_qty, pyme) if consume else []
    return ProductionPreviewOut(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        yield_unit=recipe.yield_unit.value,
        add_qty=Decimal(data.confirmed_qty),
        product_stock_qty=recipe.stock_qty + data.confirmed_qty,
        consume_ingredients=consume,
        consumed=[_consumed_out(ing, qty, ing.stock_qty - qty) for ing, qty in used],
    )


def confirm_production(
    db: Session, data: ProductionCreate, client_op_id: uuid.UUID | None
) -> tuple[ProductionOut, bool]:
    """Guarda lo detectado y lo confirmado, suma el producto a las existencias y, si corresponde, descuenta los
    insumos usados. Todo en una transacción. Con la misma clave devuelve el original (replayed=True)."""
    if client_op_id is not None and (existing := _by_op(db, client_op_id)) is not None:
        return production_out(db, existing), True
    recipe = _final_recipe(db, data.recipe_id)
    pyme = _pyme(db)
    consume = pyme.production_consumes_ingredients if data.consume_ingredients is None else data.consume_ingredients
    record = ProductionRecord(
        recipe_id=recipe.id,
        detected_qty=data.detected_qty,
        confirmed_qty=data.confirmed_qty,
        model_version=data.model_version,
        detections={"items": [d.model_dump() for d in data.detections]} if data.detections else None,
        was_corrected=data.detected_qty is not None and data.detected_qty != data.confirmed_qty,
        client_op_id=client_op_id,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:  # otra solicitud con la misma clave ganó la carrera
        db.rollback()
        if client_op_id is None or (existing := _by_op(db, client_op_id)) is None:
            raise ProblemError(409, "production_conflict", "No se pudo guardar la producción") from None
        return production_out(db, existing), True
    ref = (PRODUCTION_REF, record.id)
    consumed: list[ConsumedOut] = []
    if data.confirmed_qty > 0:
        apply_product_movement(
            db, recipe, Decimal(data.confirmed_qty), ProductMovementReason.PRODUCTION, note="Producción", reference=ref
        )
        if consume:
            note = f"Producción: {recipe.name} × {data.confirmed_qty}"
            for ing, qty in _consumption(db, recipe, data.confirmed_qty, pyme):
                apply_system_movement(db, ing, -qty, MovementReason.PRODUCTION, note, ref)
                consumed.append(_consumed_out(ing, qty, ing.stock_qty))
    record.consumed_ingredients = bool(consumed)
    # "¿cuánto produje hoy?", "¿cuántas tengo listas?" y el stock de insumos cambian: se invalida la caché.
    bump(db, DataDomain.PRODUCTION, *([DataDomain.INVENTORY] if consumed else []))
    db.commit()
    db.refresh(record)
    db.refresh(recipe)
    out = ProductionOut.model_validate(record)
    return out.model_copy(
        update={"recipe_name": recipe.name, "product_stock_qty": recipe.stock_qty, "consumed": consumed}
    ), False


def production_out(db: Session, record: ProductionRecord) -> ProductionOut:
    """Respuesta de una producción ya guardada (reintento o historial), con lo que descontó."""
    recipe = db.get(Recipe, record.recipe_id)
    rows = db.execute(
        select(StockMovement, Ingredient)
        .join(
            Ingredient, (Ingredient.id == StockMovement.ingredient_id) & (Ingredient.pyme_id == StockMovement.pyme_id)
        )
        .where(
            StockMovement.reference_type == PRODUCTION_REF,
            StockMovement.reference_id == record.id,
            StockMovement.delta_qty < 0,
        )
        .order_by(Ingredient.name)
    ).all()
    out = ProductionOut.model_validate(record)
    return out.model_copy(
        update={
            "recipe_name": recipe.name if recipe else None,
            "product_stock_qty": recipe.stock_qty if recipe else None,
            "consumed": [_consumed_out(ing, -m.delta_qty, ing.stock_qty) for m, ing in rows],
        }
    )


def get_production(db: Session, production_id: uuid.UUID) -> ProductionRecord:
    record = db.get(ProductionRecord, production_id)
    if record is None:
        raise not_found("production_not_found", "No encontramos esa producción")
    return record


def void_production(db: Session, production_id: uuid.UUID) -> ProductionRecord:
    """Anula una producción con movimientos inversos (el libro no se reescribe). Anular dos veces no hace nada."""
    record = get_production(db, production_id)
    if record.voided_at is not None:
        return record
    ref = (PRODUCTION_REF, record.id)
    recipe = db.get(Recipe, record.recipe_id)
    product_net = db.scalar(
        select(func.coalesce(func.sum(ProductMovement.delta_qty), 0)).where(
            ProductMovement.reference_type == PRODUCTION_REF, ProductMovement.reference_id == record.id
        )
    )
    if recipe is not None and product_net:
        apply_product_movement(
            db,
            recipe,
            -Decimal(product_net),
            ProductMovementReason.VOID,
            note="Anulación de la producción",
            reference=ref,
        )
    stock_net = db.execute(
        select(StockMovement.ingredient_id, func.sum(StockMovement.delta_qty))
        .where(StockMovement.reference_type == PRODUCTION_REF, StockMovement.reference_id == record.id)
        .group_by(StockMovement.ingredient_id)
    ).all()
    for ingredient_id, net in stock_net:
        ing = db.get(Ingredient, ingredient_id)
        if ing is not None and net:
            apply_system_movement(db, ing, -net, MovementReason.PRODUCTION, VOID_NOTE, ref)
    record.voided_at = datetime.now(UTC)
    bump(db, DataDomain.PRODUCTION, DataDomain.INVENTORY)
    db.commit()
    db.refresh(record)
    return record


def list_productions(db: Session, limit: int, cursor: str | None) -> tuple[list[ProductionOut], str | None]:
    """Historial de producción, de la más reciente a la más antigua, con el nombre del producto."""
    stmt = select(ProductionRecord, Recipe.name).join(
        Recipe, (Recipe.id == ProductionRecord.recipe_id) & (Recipe.pyme_id == ProductionRecord.pyme_id)
    )
    after = decode_cursor(cursor)
    if after:
        stmt = stmt.where(
            tuple_(ProductionRecord.created_at, ProductionRecord.id)
            < tuple_(datetime.fromisoformat(after[0]), uuid.UUID(after[1]))
        )
    rows = db.execute(
        stmt.order_by(ProductionRecord.created_at.desc(), ProductionRecord.id.desc()).limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [ProductionOut.model_validate(r).model_copy(update={"recipe_name": name}) for r, name in rows]
    last = rows[-1][0] if rows else None
    next_cursor = encode_cursor([last.created_at.isoformat(), str(last.id)]) if has_more and last else None
    return items, next_cursor

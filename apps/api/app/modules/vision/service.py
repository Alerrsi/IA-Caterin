import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ProblemError, not_found
from app.db.models import ProductionRecord, Recipe
from app.modules.vision.detector import Detection
from app.modules.vision.schemas import CountLine, ProductionCreate


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


def confirm_production(
    db: Session, data: ProductionCreate, client_op_id: uuid.UUID | None
) -> tuple[ProductionRecord, bool]:
    """Guarda lo detectado y lo confirmado. Con la misma clave devuelve el original (replayed=True)."""
    if client_op_id is not None and (existing := _by_op(db, client_op_id)) is not None:
        return existing, True
    recipe = db.get(Recipe, data.recipe_id)
    if recipe is None or not recipe.is_final_product:
        raise not_found("recipe_not_found", "No encontramos ese producto")
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
        db.commit()
    except IntegrityError:  # otra solicitud con la misma clave ganó la carrera
        db.rollback()
        if client_op_id is None or (existing := _by_op(db, client_op_id)) is None:
            raise ProblemError(409, "production_conflict", "No se pudo guardar la producción") from None
        return existing, True
    db.refresh(record)
    return record, False

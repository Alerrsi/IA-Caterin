import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.http import DEFAULT_LIMIT, CursorQuery, LimitQuery, Page, idempotency_key
from app.core.tenancy import CurrentUserDep, OwnerDep, TenantDB
from app.modules.vision import service
from app.modules.vision.detector import Detector, InvalidImageError, get_detector
from app.modules.vision.schemas import (
    CountOut,
    DetectionOut,
    ModelOut,
    ProductionCreate,
    ProductionOut,
    ProductionPreviewIn,
    ProductionPreviewOut,
)

router = APIRouter(prefix="/vision", tags=["visión"])
DetectorDep = Annotated[Detector | None, Depends(get_detector)]


@router.get("/model", response_model=ModelOut)
def model_info(_user: CurrentUserDep, detector: DetectorDep) -> ModelOut:
    if detector is None:
        return ModelOut(loaded=False)
    return ModelOut(loaded=True, **detector.info.__dict__)


@router.post("/count", response_model=CountOut)
def count(_user: CurrentUserDep, db: TenantDB, detector: DetectorDep, image: Annotated[UploadFile, File()]) -> CountOut:
    """Foto -> conteo por producto. La foto no se guarda; la usuaria corrige y confirma en `/productions`."""
    if detector is None:
        raise ProblemError(
            503, "vision_model_unavailable", "El conteo por foto no está disponible por ahora", "Cuenta a mano."
        )
    settings = get_settings()
    data = image.file.read(settings.vision_max_image_mb * 1024 * 1024 + 1)
    if len(data) > settings.vision_max_image_mb * 1024 * 1024:
        raise ProblemError(413, "image_too_large", "La foto es demasiado grande")
    start = time.perf_counter()
    try:
        detections = detector.detect(data, settings.vision_threshold)
    except InvalidImageError:
        raise ProblemError(415, "invalid_image", "No pudimos leer esa foto", "Prueba con una JPG o PNG.") from None
    return CountOut(
        model_version=detector.info.version,
        counts=service.count_by_class(db, detections),
        detections=[DetectionOut(vision_class=d.vision_class, score=d.score, box=d.box) for d in detections],
        elapsed_ms=round((time.perf_counter() - start) * 1000),
    )


@router.post("/productions/preview", response_model=ProductionPreviewOut)
def preview_production(data: ProductionPreviewIn, _user: CurrentUserDep, db: TenantDB) -> ProductionPreviewOut:
    """Lo que sumaría a las existencias y los insumos que descontaría confirmar. No guarda nada (T18)."""
    return service.preview_production(db, data)


@router.get("/productions", response_model=Page[ProductionOut])
def list_productions(
    _user: CurrentUserDep, db: TenantDB, limit: LimitQuery = DEFAULT_LIMIT, cursor: CursorQuery = None
) -> Page[ProductionOut]:
    """Historial de producción, de la más reciente a la más antigua."""
    items, next_cursor = service.list_productions(db, limit, cursor)
    return Page[ProductionOut](items=items, next_cursor=next_cursor)


@router.post("/productions", response_model=ProductionOut, status_code=status.HTTP_201_CREATED)
def confirm_production(
    data: ProductionCreate,
    response: Response,
    _user: CurrentUserDep,
    db: TenantDB,
    client_op_id: Annotated[uuid.UUID | None, Depends(idempotency_key)],
) -> ProductionOut:
    """Confirma la producción con la cantidad corregida: suma el producto a las existencias y descuenta los insumos
    de la receta (si la pyme lo tiene activo o `consume_ingredients` lo pide). Con `Idempotency-Key`, un reintento
    no duplica nada."""
    out, replayed = service.confirm_production(db, data, client_op_id)
    if replayed:
        response.status_code = status.HTTP_200_OK
    return out.model_copy(update={"replayed": replayed})


@router.post("/productions/{production_id}/void", response_model=ProductionOut)
def void_production(production_id: uuid.UUID, _owner: OwnerDep, db: TenantDB) -> ProductionOut:
    """Anula una producción: devuelve los insumos y resta el producto con movimientos inversos. Solo la dueña."""
    record = service.void_production(db, production_id)
    return service.production_out(db, record)

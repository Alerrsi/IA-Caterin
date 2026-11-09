import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.http import idempotency_key
from app.core.tenancy import CurrentUserDep, TenantDB
from app.modules.vision import service
from app.modules.vision.detector import Detector, InvalidImageError, get_detector
from app.modules.vision.schemas import CountOut, DetectionOut, ModelOut, ProductionCreate, ProductionOut

router = APIRouter(prefix="/vision", tags=["visión"])
DetectorDep = Annotated[Detector | None, Depends(get_detector)]


@router.get("/model", response_model=ModelOut)
def model_info(_user: CurrentUserDep, detector: DetectorDep) -> ModelOut:
    if detector is None:
        return ModelOut(loaded=False)
    return ModelOut(loaded=True, **detector.info.__dict__)


@router.post("/count", response_model=CountOut)
def count(_user: CurrentUserDep, db: TenantDB, detector: DetectorDep, photo: Annotated[UploadFile, File()]) -> CountOut:
    """Foto -> conteo por producto. La foto no se guarda; la usuaria corrige y confirma en `/productions`."""
    if detector is None:
        raise ProblemError(
            503, "vision_model_unavailable", "El conteo por foto no está disponible por ahora", "Cuenta a mano."
        )
    settings = get_settings()
    image = photo.file.read(settings.vision_max_image_mb * 1024 * 1024 + 1)
    if len(image) > settings.vision_max_image_mb * 1024 * 1024:
        raise ProblemError(413, "image_too_large", "La foto es demasiado grande")
    start = time.perf_counter()
    try:
        detections = detector.detect(image, settings.vision_threshold)
    except InvalidImageError:
        raise ProblemError(415, "invalid_image", "No pudimos leer esa foto", "Prueba con una JPG o PNG.") from None
    return CountOut(
        model_version=detector.info.version,
        counts=service.count_by_class(db, detections),
        detections=[DetectionOut(vision_class=d.vision_class, score=d.score, box=d.box) for d in detections],
        elapsed_ms=round((time.perf_counter() - start) * 1000),
    )


@router.post("/productions", response_model=ProductionOut, status_code=status.HTTP_201_CREATED)
def confirm_production(
    data: ProductionCreate,
    response: Response,
    _user: CurrentUserDep,
    db: TenantDB,
    client_op_id: Annotated[uuid.UUID | None, Depends(idempotency_key)],
) -> ProductionOut:
    """Confirma la producción con la cantidad corregida. Con `Idempotency-Key`, un reintento no duplica."""
    record, replayed = service.confirm_production(db, data, client_op_id)
    if replayed:
        response.status_code = status.HTTP_200_OK
    return ProductionOut.model_validate(record).model_copy(update={"replayed": replayed})

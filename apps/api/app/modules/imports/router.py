import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from app.core.errors import ProblemError
from app.core.tenancy import CurrentUserDep, TenantDB
from app.modules.imports import service
from app.modules.imports.parsing import MAX_BYTES
from app.modules.imports.service import (
    ImportResult,
    IngredientConfirm,
    IngredientPreview,
    PriceConfirm,
    PricePreview,
    UndoResult,
)

router = APIRouter(prefix="/imports", tags=["importar planillas"])

TEMPLATES = {"ingredients": service.INGREDIENT_TEMPLATE, "prices": service.PRICE_TEMPLATE}


async def _read(file: UploadFile) -> bytes:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ProblemError(413, "file_too_large", "El archivo es demasiado grande", "El máximo es 5 MB.")
    return data


@router.get("/templates/{kind}.csv", response_class=Response)
def template(kind: str) -> Response:
    """Planilla de ejemplo (separador `;`, se abre bien en Excel en español)."""
    if kind not in TEMPLATES:
        raise ProblemError(404, "template_not_found", "No existe esa plantilla")
    return Response(
        ("﻿" + TEMPLATES[kind]).encode(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="plantilla_{kind}.csv"'},
    )


@router.post("/ingredients/preview", response_model=IngredientPreview)
async def preview_ingredients(_user: CurrentUserDep, db: TenantDB, file: UploadFile = File(...)) -> IngredientPreview:  # noqa: B008
    """Lee la planilla y muestra qué filas se pueden importar y cuáles tienen errores. No guarda nada."""
    return service.preview_ingredients(db, file.filename or "", await _read(file))


@router.post("/ingredients/confirm", response_model=ImportResult, status_code=201)
def confirm_ingredients(data: IngredientConfirm, _user: CurrentUserDep, db: TenantDB) -> ImportResult:
    return service.confirm_ingredients(db, data)


@router.post("/prices/preview", response_model=PricePreview)
async def preview_prices(_user: CurrentUserDep, db: TenantDB, file: UploadFile = File(...)) -> PricePreview:  # noqa: B008
    return service.preview_prices(db, file.filename or "", await _read(file))


@router.post("/prices/confirm", response_model=ImportResult, status_code=201)
def confirm_prices(data: PriceConfirm, _user: CurrentUserDep, db: TenantDB) -> ImportResult:
    return service.confirm_prices(db, data)


@router.delete("/{import_batch_id}", response_model=UndoResult)
def undo_import(import_batch_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> UndoResult:
    """Deshace una importación confirmada, si sus datos todavía no se usaron."""
    return service.undo_import(db, import_batch_id)

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.http import DEFAULT_LIMIT, CursorQuery, LimitQuery, Page, etag_json, idempotency_key
from app.core.tenancy import CurrentUserDep, TenantDB
from app.db.models import Ingredient
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    IngredientCreate,
    IngredientOut,
    IngredientUpdate,
    MovementCreate,
    MovementOut,
    MovementResult,
)

router = APIRouter(tags=["inventario"])


@router.get("/ingredients", response_model=Page[IngredientOut])
def list_ingredients(
    request: Request,
    _user: CurrentUserDep,
    db: TenantDB,
    q: str | None = None,
    limit: LimitQuery = DEFAULT_LIMIT,
    cursor: CursorQuery = None,
    updated_since: datetime | None = None,
    include_inactive: bool = False,
    low_only: bool = False,
) -> Response:
    """Insumos con su stock, ordenados por nombre. Revalida con ETag para ahorrar datos."""
    page = service.list_ingredients(db, q, limit, cursor, updated_since, include_inactive, low_only)
    return etag_json(request, page)


@router.post("/ingredients", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
def create_ingredient(data: IngredientCreate, _user: CurrentUserDep, db: TenantDB) -> Ingredient:
    ing = service.create_ingredient(db, data)
    db.commit()
    db.refresh(ing)
    return ing


@router.get("/ingredients/{ingredient_id}", response_model=IngredientOut)
def get_ingredient(ingredient_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> Ingredient:
    return service.get_ingredient(db, ingredient_id)


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: uuid.UUID, data: IngredientUpdate, _user: CurrentUserDep, db: TenantDB
) -> Ingredient:
    return service.update_ingredient(db, ingredient_id, data)


@router.delete("/ingredients/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_ingredient(ingredient_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> Response:
    """Desactiva el insumo (no se borra: puede estar en recetas o cotizaciones antiguas)."""
    service.update_ingredient(db, ingredient_id, IngredientUpdate(is_active=False))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ingredients/{ingredient_id}/movements", response_model=Page[MovementOut])
def list_movements(
    ingredient_id: uuid.UUID,
    _user: CurrentUserDep,
    db: TenantDB,
    limit: LimitQuery = DEFAULT_LIMIT,
    cursor: CursorQuery = None,
) -> Page[MovementOut]:
    rows, next_cursor = service.list_movements(db, ingredient_id, limit, cursor)
    return Page[MovementOut](items=[MovementOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.post("/stock/movements", response_model=MovementResult, status_code=status.HTTP_201_CREATED)
def record_movement(
    data: MovementCreate,
    response: Response,
    _user: CurrentUserDep,
    db: TenantDB,
    client_op_id: Annotated[uuid.UUID | None, Depends(idempotency_key)],
) -> MovementResult:
    """Entrada, salida, ajuste o merma. Con `Idempotency-Key`, un reintento no duplica el movimiento."""
    movement, ing, replayed = service.record_movement(db, data, client_op_id)
    if replayed:
        response.status_code = status.HTTP_200_OK
    return MovementResult(
        movement=MovementOut.model_validate(movement),
        ingredient=IngredientOut.model_validate(ing),
        went_negative=ing.stock_qty < 0,
        replayed=replayed,
    )


@router.get("/stock/low", response_model=list[IngredientOut])
def low_stock(_user: CurrentUserDep, db: TenantDB) -> list[Ingredient]:
    return service.list_low_stock(db)

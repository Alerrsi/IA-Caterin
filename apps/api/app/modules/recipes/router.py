import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.tenancy import CurrentUserDep, TenantDB
from app.modules.recipes import service
from app.modules.recipes.schemas import RecipeCostOut, RecipeCreate, RecipeOut, RecipeSummary, RecipeUpdate

router = APIRouter(tags=["recetas"])


@router.get("/recipes", response_model=list[RecipeSummary])
def list_recipes(
    _user: CurrentUserDep, db: TenantDB, q: str | None = None, include_inactive: bool = False
) -> list[RecipeSummary]:
    return [RecipeSummary.model_validate(r) for r in service.list_recipes(db, q, include_inactive)]


@router.post("/recipes", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def create_recipe(data: RecipeCreate, _user: CurrentUserDep, db: TenantDB) -> RecipeOut:
    return service.to_out(db, service.create_recipe(db, data))


@router.get("/recipes/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> RecipeOut:
    return service.to_out(db, service.get_recipe(db, recipe_id))


@router.patch("/recipes/{recipe_id}", response_model=RecipeOut)
def update_recipe(recipe_id: uuid.UUID, data: RecipeUpdate, _user: CurrentUserDep, db: TenantDB) -> RecipeOut:
    """Si cambian las líneas o el rendimiento, sube la versión de la receta."""
    return service.to_out(db, service.update_recipe(db, recipe_id, data))


@router.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_recipe(recipe_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> Response:
    service.update_recipe(db, recipe_id, RecipeUpdate(is_active=False))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/recipes/{recipe_id}/cost", response_model=RecipeCostOut)
def recipe_cost(
    recipe_id: uuid.UUID,
    _user: CurrentUserDep,
    db: TenantDB,
    qty: Annotated[
        Decimal | None, Query(gt=0, le=100000, description="Unidades a producir; por defecto, el rendimiento")
    ] = None,
) -> RecipeCostOut:
    """Costo de producir `qty` unidades con los precios vigentes más baratos (con IVA).

    Lo calcula el código, no la IA (ADR-002).
    """
    recipe = service.get_recipe(db, recipe_id)
    return service.cost_out(recipe, service.compute_cost(db, recipe, qty))

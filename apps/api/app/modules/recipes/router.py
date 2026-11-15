import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.core import media
from app.core.tenancy import CurrentUserDep, OwnerDep, TenantDB
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


@router.put("/recipes/{recipe_id}/photo", response_model=RecipeOut)
def upload_photo(
    recipe_id: uuid.UUID, owner: OwnerDep, db: TenantDB, image: Annotated[UploadFile, File()]
) -> RecipeOut:
    """Foto del producto para el catálogo del portal (ADR-009). Solo la dueña decide qué se publica. JPG, PNG o WebP
    de hasta 2 MB; se guarda como WebP de 800 px, sin metadatos (EXIF con ubicación incluido)."""
    service.get_recipe(db, recipe_id)  # 404 antes de guardar el archivo si la receta no es de esta pyme
    path = media.save_image(owner.pyme_id, media.read_upload(image.file), media.Kind.PHOTO)
    return service.to_out(db, service.set_photo(db, recipe_id, path))


@router.delete("/recipes/{recipe_id}/photo", response_model=RecipeOut)
def delete_photo(recipe_id: uuid.UUID, _owner: OwnerDep, db: TenantDB) -> RecipeOut:
    return service.to_out(db, service.set_photo(db, recipe_id, None))


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

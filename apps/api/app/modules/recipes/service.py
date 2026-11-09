"""Recetas y su costo calculado. La aritmética está en `costing.py` (funciones puras)."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.units import quantize_qty
from app.db.enums import DataDomain
from app.db.models import Ingredient, Pyme, Recipe, RecipeLine
from app.modules.inventory.service import convert_qty
from app.modules.recipes.costing import CostLineInput, RecipeCost, effective_waste, recipe_cost
from app.modules.recipes.schemas import (
    CostLineOut,
    RecipeCostOut,
    RecipeCreate,
    RecipeLineIn,
    RecipeOut,
    RecipeUpdate,
)
from app.modules.suppliers.service import current_options

_DUPLICATE = ProblemError(409, "recipe_exists", "Ya tienes una receta con ese nombre o esa clase de visión")


def list_recipes(db: Session, q: str | None = None, include_inactive: bool = False) -> list[Recipe]:
    stmt = select(Recipe).order_by(func.lower(Recipe.name))
    if not include_inactive:
        stmt = stmt.where(Recipe.is_active)
    if q:
        stmt = stmt.where(Recipe.name.ilike(f"%{q.strip()}%"))
    return list(db.scalars(stmt))


def get_recipe(db: Session, recipe_id: uuid.UUID) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise not_found("recipe_not_found", "No encontramos esa receta")
    return recipe


def _ingredients(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Ingredient]:
    found = {i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.id.in_(ids)))}
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise ProblemError(
            422,
            "ingredient_not_found",
            "Uno de los insumos de la receta no existe",
            errors=[{"field": "lines", "message": f"Insumo {m} no encontrado"} for m in missing],
        )
    return found


def _build_lines(db: Session, lines: list[RecipeLineIn]) -> list[RecipeLine]:
    ingredients = _ingredients(db, [line.ingredient_id for line in lines])
    return [
        RecipeLine(
            ingredient_id=line.ingredient_id,
            qty=quantize_qty(convert_qty(line.qty, line.unit, ingredients[line.ingredient_id])),
            waste_pct=line.waste_pct,
        )
        for line in lines
    ]


def _commit(db: Session) -> None:
    try:
        bump(db, DataDomain.RECIPES)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _DUPLICATE from exc


def create_recipe(db: Session, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        name=" ".join(data.name.split()),
        yield_qty=data.yield_qty,
        yield_unit=data.yield_unit,
        is_final_product=data.is_final_product,
        vision_class=data.vision_class,
        notes=data.notes,
        version=1,
    )
    db.add(recipe)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _DUPLICATE from exc
    for line in _build_lines(db, data.lines):
        line.pyme_id = recipe.pyme_id
        line.recipe_id = recipe.id
        db.add(line)
    _commit(db)
    db.refresh(recipe)
    return recipe


def update_recipe(db: Session, recipe_id: uuid.UUID, data: RecipeUpdate) -> Recipe:
    recipe = get_recipe(db, recipe_id)
    changes = data.model_dump(exclude_unset=True, exclude={"lines"})
    for field, value in changes.items():
        if value is None and field not in ("vision_class", "notes"):
            continue
        setattr(recipe, field, " ".join(value.split()) if field == "name" else value)
    if data.lines is not None:
        new_lines = _build_lines(db, data.lines)
        recipe.lines.clear()
        db.flush()
        recipe.lines.extend(new_lines)
        recipe.version += 1
    elif "yield_qty" in changes:
        recipe.version += 1
    _commit(db)
    db.refresh(recipe)
    return recipe


def to_out(db: Session, recipe: Recipe) -> RecipeOut:
    ingredients = {
        i.id: i
        for i in db.scalars(select(Ingredient).where(Ingredient.id.in_([ln.ingredient_id for ln in recipe.lines])))
    }
    out = RecipeOut.model_validate(recipe)
    for line in out.lines:
        ing = ingredients.get(line.ingredient_id)
        if ing:
            line.ingredient_name = ing.name
            line.base_unit = ing.base_unit
    return out


def compute_cost(db: Session, recipe: Recipe, units: Decimal | None = None) -> RecipeCost:
    pyme = db.get(Pyme, recipe.pyme_id)
    assert pyme is not None  # noqa: S101 - la receta pertenece a una pyme existente
    ids = [line.ingredient_id for line in recipe.lines]
    ingredients = {i.id: i for i in db.scalars(select(Ingredient).where(Ingredient.id.in_(ids)))}
    options = current_options(db, ids)
    inputs = [
        CostLineInput(
            ingredient_id=line.ingredient_id,
            ingredient_name=ingredients[line.ingredient_id].name,
            base_unit=ingredients[line.ingredient_id].base_unit,
            qty_per_yield=line.qty,
            waste_pct=effective_waste(
                line.waste_pct, ingredients[line.ingredient_id].waste_pct, pyme.default_waste_pct
            ),
            options=options.get(line.ingredient_id, []),
        )
        for line in recipe.lines
    ]
    return recipe_cost(inputs, recipe.yield_qty, units or recipe.yield_qty, pyme.vat_pct)


def cost_out(recipe: Recipe, cost: RecipeCost) -> RecipeCostOut:
    return RecipeCostOut(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        units=cost.units,
        yield_unit=recipe.yield_unit,
        total_clp=int(cost.total_clp),
        per_unit_clp=int(cost.per_unit_clp) if cost.per_unit_clp is not None else None,
        is_complete=cost.is_complete,
        missing_prices=cost.missing_prices,
        lines=[
            CostLineOut(
                ingredient_id=line.ingredient_id,
                ingredient_name=line.ingredient_name,
                base_unit=line.base_unit,
                required_qty=line.required_qty,
                waste_pct=line.waste_pct,
                supplier_name=line.price.supplier_name if line.price else None,
                package_label=line.price.package_label if line.price else None,
                price_date=line.price.price_date if line.price else None,
                price_id=line.price.price_id if line.price else None,
                unit_price_clp=line.unit_price_clp.quantize(Decimal("0.0001")) if line.unit_price_clp else None,
                cost_clp=int(line.cost_clp) if line.cost_clp is not None else None,
            )
            for line in cost.lines
        ],
    )

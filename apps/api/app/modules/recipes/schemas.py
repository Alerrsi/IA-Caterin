import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.db.enums import BaseUnit


class RecipeLineIn(BaseModel):
    ingredient_id: uuid.UUID
    qty: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str | None = Field(default=None, description="Unidad de qty (kg, g, cc, docena…); por defecto la base")
    waste_pct: Decimal | None = Field(default=None, ge=0, lt=100)


def _unique_lines(lines: list[RecipeLineIn] | None) -> list[RecipeLineIn] | None:
    if lines is not None:
        ids = [line.ingredient_id for line in lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Un insumo aparece dos veces en la receta")
    return lines


class RecipeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    yield_qty: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    yield_unit: BaseUnit = BaseUnit.UNIT
    is_final_product: bool = True
    vision_class: str | None = Field(default=None, max_length=60, pattern=r"^[a-z0-9_]+$")
    notes: str | None = Field(default=None, max_length=2000)
    lines: Annotated[list[RecipeLineIn], Field(min_length=1, max_length=60), AfterValidator(_unique_lines)]


class RecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    yield_qty: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    yield_unit: BaseUnit | None = None
    is_final_product: bool | None = None
    vision_class: str | None = Field(default=None, max_length=60, pattern=r"^[a-z0-9_]+$")
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    lines: Annotated[list[RecipeLineIn] | None, Field(min_length=1, max_length=60), AfterValidator(_unique_lines)] = (
        None
    )


class RecipeLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str = ""
    base_unit: BaseUnit | None = None
    qty: Decimal
    waste_pct: Decimal | None


class RecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    yield_qty: Decimal
    yield_unit: BaseUnit
    is_final_product: bool
    vision_class: str | None
    notes: str | None
    version: int
    is_active: bool
    updated_at: datetime
    lines: list[RecipeLineOut]


class RecipeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    yield_qty: Decimal
    yield_unit: BaseUnit
    is_final_product: bool
    vision_class: str | None
    is_active: bool
    updated_at: datetime


class CostLineOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    base_unit: BaseUnit
    required_qty: Decimal
    waste_pct: Decimal
    supplier_name: str | None
    package_label: str | None
    price_date: date | None
    price_id: uuid.UUID | None
    unit_price_clp: Decimal | None = Field(description="Con IVA, por unidad base")
    cost_clp: int | None


class RecipeCostOut(BaseModel):
    recipe_id: uuid.UUID
    recipe_name: str
    units: Decimal
    yield_unit: BaseUnit
    total_clp: int
    per_unit_clp: int | None
    is_complete: bool
    missing_prices: list[str]
    vat_included: bool = True
    lines: list[CostLineOut]

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.enums import BaseUnit, MovementReason

Name = Field(min_length=2, max_length=120)


class IngredientCreate(BaseModel):
    name: str = Name
    base_unit: BaseUnit
    initial_stock: Decimal = Field(default=Decimal(0), ge=0, max_digits=14, decimal_places=3)
    min_stock_qty: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    waste_pct: Decimal | None = Field(default=None, ge=0, lt=100)
    density_g_per_ml: Decimal | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=60)


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    min_stock_qty: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    waste_pct: Decimal | None = Field(default=None, ge=0, lt=100)
    density_g_per_ml: Decimal | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_unit: BaseUnit
    stock_qty: Decimal
    min_stock_qty: Decimal | None
    waste_pct: Decimal | None
    density_g_per_ml: Decimal | None
    category: str | None
    is_active: bool
    is_low: bool = False
    updated_at: datetime

    @model_validator(mode="after")
    def _low(self) -> "IngredientOut":
        self.is_low = self.min_stock_qty is not None and self.stock_qty < self.min_stock_qty
        return self


class MovementCreate(BaseModel):
    ingredient_id: uuid.UUID
    reason: MovementReason
    delta_qty: Decimal = Field(max_digits=14, decimal_places=3, description="Positivo entra, negativo sale")
    unit: str | None = Field(default=None, description="Unidad de delta_qty (kg, g, l, docena…); por defecto la base")
    note: str | None = Field(default=None, max_length=200)
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def _sign(self) -> "MovementCreate":
        if self.delta_qty == 0:
            raise ValueError("La cantidad no puede ser cero")
        if self.reason == MovementReason.PURCHASE and self.delta_qty < 0:
            raise ValueError("Una compra debe sumar stock")
        if self.reason in (MovementReason.CONSUMPTION, MovementReason.WASTE) and self.delta_qty > 0:
            raise ValueError("Un consumo o una merma debe restar stock")
        if self.reason in (MovementReason.IMPORT, MovementReason.PRODUCTION):
            raise ValueError("Ese tipo de movimiento lo registra el sistema")
        return self


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    delta_qty: Decimal
    reason: MovementReason
    note: str | None
    occurred_at: datetime
    created_at: datetime


class MovementResult(BaseModel):
    movement: MovementOut
    ingredient: IngredientOut
    went_negative: bool
    replayed: bool = False

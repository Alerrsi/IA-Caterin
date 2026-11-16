import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DetectionOut(BaseModel):
    vision_class: str
    score: float
    box: tuple[float, float, float, float]


class CountLine(BaseModel):
    vision_class: str
    count: int
    recipe_id: uuid.UUID | None = Field(None, description="None si ningún producto usa esa clase")
    recipe_name: str | None = None


class CountOut(BaseModel):
    model_version: str
    counts: list[CountLine]
    detections: list[DetectionOut]
    elapsed_ms: int


class ModelOut(BaseModel):
    loaded: bool
    version: str | None = None
    classes: list[str] = []
    input_size: int | None = None
    sha256: str | None = None


class ProductionCreate(BaseModel):
    recipe_id: uuid.UUID
    confirmed_qty: int = Field(ge=0, le=100000)
    detected_qty: int | None = Field(None, ge=0, le=100000)
    model_version: str | None = Field(None, max_length=60)
    detections: list[DetectionOut] | None = Field(None, max_length=1000)
    consume_ingredients: bool | None = Field(
        None, description="Descontar los insumos de la receta. Sin valor, se usa el ajuste de la pyme (T18)"
    )


class ProductionPreviewIn(BaseModel):
    recipe_id: uuid.UUID
    confirmed_qty: int = Field(ge=0, le=100000)
    consume_ingredients: bool | None = None


class ConsumedOut(BaseModel):
    """Un insumo descontado (o por descontar) por una producción, con el saldo que queda."""

    ingredient_id: uuid.UUID
    name: str
    base_unit: str
    qty: Decimal = Field(description="Cantidad usada, en unidad base, con merma")
    stock_qty: Decimal = Field(description="Saldo del insumo después de descontar")
    went_negative: bool


class ProductionPreviewOut(BaseModel):
    recipe_id: uuid.UUID
    recipe_name: str
    yield_unit: str
    add_qty: Decimal
    product_stock_qty: Decimal = Field(description="Existencias del producto después de sumar")
    consume_ingredients: bool
    consumed: list[ConsumedOut]


class ProductionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipe_id: uuid.UUID
    recipe_name: str | None = None
    detected_qty: int | None
    confirmed_qty: int
    model_version: str | None
    was_corrected: bool
    consumed_ingredients: bool
    voided_at: datetime | None
    created_at: datetime
    product_stock_qty: Decimal | None = Field(None, description="Existencias del producto tras esta operación")
    consumed: list[ConsumedOut] = []
    replayed: bool = False

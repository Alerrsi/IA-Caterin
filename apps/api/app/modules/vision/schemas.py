import uuid
from datetime import datetime

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


class ProductionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipe_id: uuid.UUID
    detected_qty: int | None
    confirmed_qty: int
    model_version: str | None
    was_corrected: bool
    created_at: datetime
    replayed: bool = False

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.enums import BaseUnit, PriceSourceKind


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=200)
    delivery_days: list[int] | None = Field(default=None, description="1 = lunes … 7 = domingo")
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("delivery_days")
    @classmethod
    def _days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(d < 1 or d > 7 for d in value):
            raise ValueError("Los días van de 1 (lunes) a 7 (domingo)")
        return sorted(set(value))


class SupplierUpdate(SupplierCreate):
    name: str | None = Field(default=None, min_length=2, max_length=120)  # type: ignore[assignment]
    is_active: bool | None = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    website: str | None
    delivery_days: list[int] | None
    notes: str | None
    is_active: bool
    updated_at: datetime


class PriceCreate(BaseModel):
    ingredient_id: uuid.UUID
    supplier_id: uuid.UUID
    package_label: str = Field(min_length=1, max_length=80, description='Presentación, p. ej. "saco 25 kg"')
    package_qty: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    package_unit: str | None = Field(default=None, description="Unidad de package_qty; por defecto la base del insumo")
    price_clp: int = Field(ge=0, le=999_999_999)
    includes_vat: bool = True
    price_date: date


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    supplier_id: uuid.UUID
    package_label: str
    package_qty: Decimal
    price_clp: int
    includes_vat: bool
    price_date: date
    source: PriceSourceKind
    is_current: bool
    created_at: datetime


class PriceComparisonItem(BaseModel):
    price_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    package_label: str
    package_qty: Decimal
    price_clp: int
    includes_vat: bool
    price_date: date
    gross_price_clp: int
    price_per_base_unit_clp: Decimal = Field(description="Con IVA, por g, ml o unidad")
    price_per_reference_clp: int = Field(description="Con IVA, por kg, L o unidad")
    reference_unit: str
    is_best: bool


class PriceComparison(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    base_unit: BaseUnit
    items: list[PriceComparisonItem]

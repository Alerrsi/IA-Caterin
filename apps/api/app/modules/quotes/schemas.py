import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.enums import OrderSource, OrderStatus, OrderUnit, QuoteStatus

# --------------------------------------------------------------------------- extracción (LLM)


class LLMItem(BaseModel):
    """Esquema que se le exige al LLM. Solo copia lo que dice el texto; no calcula."""

    name: str = Field(min_length=1, max_length=160)
    quantity: float = Field(gt=0, lt=1_000_000)
    unit: str | None = Field(default=None, max_length=30)


class LLMOrder(BaseModel):
    guests: int | None = Field(default=None, ge=1, le=100_000)
    event_date_text: str | None = Field(default=None, max_length=80)
    items: list[LLMItem] = Field(min_length=1, max_length=50)


class ExtractIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class Suggestion(BaseModel):
    recipe_id: uuid.UUID
    recipe_name: str
    score: float


class ExtractedLine(BaseModel):
    requested_name: str
    qty: Decimal
    unit: OrderUnit
    unit_text: str | None
    recipe_id: uuid.UUID | None
    recipe_name: str | None
    match_score: float | None
    suggestions: list[Suggestion]
    warning: str | None = None


class ExtractionOut(BaseModel):
    guests: int | None
    event_date: date | None
    event_date_text: str | None
    lines: list[ExtractedLine]
    needs_review: bool = Field(description="Hay productos sin receta asociada o con dudas")
    extraction: dict[str, Any] = Field(description="Trazabilidad: modelo, versión del prompt, intentos, latencia")


# --------------------------------------------------------------------------- pedidos


class OrderLineIn(BaseModel):
    recipe_id: uuid.UUID
    requested_name: str | None = Field(default=None, max_length=160)
    qty: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit: OrderUnit = OrderUnit.UNIT


# Estados que solo pone el portal de clientes o la decisión de la dueña (ADR-007), no un PATCH.
PORTAL_STATUSES = (OrderStatus.CUSTOMER_DRAFT, OrderStatus.REQUESTED)


def _staff_status(value: OrderStatus | None) -> OrderStatus | None:
    if value in PORTAL_STATUSES:
        raise ValueError("Ese estado lo pone el portal de clientes")
    return value


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    customer_contact: str | None = Field(default=None, max_length=120)
    event_date: date | None = None
    guests: int | None = Field(default=None, ge=1, le=100_000)
    status: OrderStatus = OrderStatus.DRAFT
    source: OrderSource = OrderSource.FORM
    raw_text: str | None = Field(default=None, max_length=2000)
    extraction: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[OrderLineIn] = Field(min_length=1, max_length=50)

    _status = field_validator("status")(_staff_status)


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=2, max_length=120)
    customer_contact: str | None = Field(default=None, max_length=120)
    event_date: date | None = None
    guests: int | None = Field(default=None, ge=1, le=100_000)
    status: OrderStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[OrderLineIn] | None = Field(default=None, min_length=1, max_length=50)

    _status = field_validator("status")(_staff_status)


class OrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipe_id: uuid.UUID | None
    recipe_name: str | None = None
    requested_name: str
    qty: Decimal
    unit: OrderUnit
    position: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_name: str
    customer_contact: str | None
    event_date: date | None
    guests: int | None
    status: OrderStatus
    source: OrderSource
    notes: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineOut]
    last_quote_id: uuid.UUID | None = None
    from_customer: bool = False  # lo pidió un cliente por el portal (ADR-007)
    submitted_at: datetime | None = None
    owner_message: str | None = None


class RequestDecision(BaseModel):
    message: str | None = Field(default=None, max_length=1000, description="Lo ve el cliente en el portal")


# --------------------------------------------------------------------------- cotizaciones


class QuoteCreate(BaseModel):
    margin_pct: Decimal | None = Field(default=None, ge=0, le=1000, description="Si no viene, el de la pyme")
    use_stock: bool = Field(default=True, description="Descontar el stock disponible de la lista de compras")
    started_at: datetime | None = Field(default=None, description="Cuándo empezó la cotización (métrica T09)")


class QuoteStatusUpdate(BaseModel):
    status: QuoteStatus


class QuoteProductOut(BaseModel):
    recipe_id: uuid.UUID
    recipe_name: str
    recipe_version: int
    requested_name: str
    qty: Decimal
    unit: OrderUnit
    unit_label: str
    cost_clp: int | None
    unit_price_clp: int | None
    subtotal_clp: int | None


class PurchaseOut(BaseModel):
    price_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    package_label: str
    package_qty: Decimal
    packages: int
    package_price_clp: int
    total_clp: int
    price_date: date


class QuoteLineOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    base_unit: str
    required_qty: Decimal
    stock_used_qty: Decimal
    to_buy_qty: Decimal
    purchase: PurchaseOut | None
    alternatives: list[PurchaseOut]
    note: str | None


class QuoteOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    version: int
    status: QuoteStatus
    created_at: datetime
    valid_until: date | None
    margin_pct: Decimal
    vat_pct: Decimal
    use_stock: bool
    is_complete: bool
    missing_prices: list[str]
    ingredients_cost_clp: int
    net_clp: int
    vat_clp: int
    total_clp: int
    shopping_total_clp: int
    calc_version: str
    products: list[QuoteProductOut]
    lines: list[QuoteLineOut]


class QuoteSummary(BaseModel):
    id: uuid.UUID
    version: int
    status: QuoteStatus
    created_at: datetime
    total_clp: int
    is_complete: bool


class ShoppingItem(BaseModel):
    ingredient_name: str
    package_label: str
    packages: int
    package_price_clp: int
    total_clp: int
    price_date: date


class ShoppingGroup(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    delivery_days: list[int] | None
    phone: str | None
    items: list[ShoppingItem]
    total_clp: int


class ShoppingList(BaseModel):
    quote_id: uuid.UUID
    groups: list[ShoppingGroup]
    without_price: list[str]
    covered_by_stock: list[str]
    total_clp: int

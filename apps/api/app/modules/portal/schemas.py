"""Esquemas del portal de clientes (ADR-007). Solo lo que el cliente final puede ver: nunca costos, margen,
insumos, proveedores ni stock."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.enums import BaseUnit, OrderSource, OrderStatus, OrderUnit
from app.modules.auth.schemas import Email, PasswordStr
from app.modules.quotes.schemas import OrderLineIn


class PortalPymeOut(BaseModel):
    name: str
    commune: str | None


class CustomerRegisterIn(BaseModel):
    code: str = Field(min_length=6, max_length=32, description="Código del enlace que comparte la pyme")
    full_name: str = Field(min_length=2, max_length=120)
    email: Email
    password: PasswordStr


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    yield_unit: BaseUnit


class RequestCreate(BaseModel):
    event_date: date | None = None
    guests: int | None = Field(default=None, ge=1, le=100_000)
    source: OrderSource = OrderSource.FORM
    raw_text: str | None = Field(default=None, max_length=2000)
    extraction: dict[str, object] | None = None
    notes: str | None = Field(default=None, max_length=2000, description="Comentarios para la pyme")
    lines: list[OrderLineIn] = Field(min_length=1, max_length=50)


class RequestLineOut(BaseModel):
    name: str
    qty: str
    unit: OrderUnit
    unit_label: str


class CustomerQuoteProduct(BaseModel):
    name: str
    qty: str
    unit_label: str
    unit_price_clp: int | None
    subtotal_clp: int | None


class CustomerQuoteOut(BaseModel):
    """Precio al cliente. Si falta un precio de insumo, los montos van en null (`is_complete=false`)."""

    version: int
    is_complete: bool
    products: list[CustomerQuoteProduct]
    net_clp: int | None
    vat_pct: str
    vat_clp: int | None
    total_clp: int | None
    valid_until: date | None


# Por qué no hay precio todavía: la pyme no definió su margen, falta el precio de un insumo o el pedido no se
# puede calcular (p. ej. porciones). En los tres casos la pyme lo revisa al recibir la solicitud.
PendingReason = Literal["margin_required", "missing_prices", "cannot_calculate"]


class RequestOut(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    created_at: datetime
    submitted_at: datetime | None
    decided_at: datetime | None
    event_date: date | None
    guests: int | None
    notes: str | None
    owner_message: str | None
    lines: list[RequestLineOut]
    quote: CustomerQuoteOut | None
    price_pending: PendingReason | None = None
    can_send: bool
    can_cancel: bool


class RequestSummary(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    created_at: datetime
    submitted_at: datetime | None
    event_date: date | None
    products: str
    total_clp: int | None

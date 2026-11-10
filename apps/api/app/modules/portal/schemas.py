"""Esquemas del portal de clientes (ADR-007). Solo lo que el cliente final puede ver: nunca costos, margen,
insumos, proveedores ni stock."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.db.enums import BaseUnit, OrderSource, OrderStatus, OrderUnit
from app.modules.auth.schemas import Email, PasswordStr
from app.modules.quotes.schemas import OrderLineIn


class PortalPymeOut(BaseModel):
    """Una pyme a la que el cliente puede cotizar (portal abierto, o ya le cotizó antes)."""

    id: uuid.UUID
    name: str
    commune: str | None
    joined: bool = Field(default=False, description="El cliente ya tiene cuenta en esta pyme")


class CustomerRegisterIn(BaseModel):
    code: str | None = Field(default=None, min_length=6, max_length=32, description="Código del enlace de la pyme")
    pyme_id: uuid.UUID | None = Field(default=None, description="O una pyme del directorio (GET /portal/directory)")
    full_name: str = Field(min_length=2, max_length=120)
    email: Email
    password: PasswordStr

    @model_validator(mode="after")
    def _one_pyme(self) -> "CustomerRegisterIn":
        if self.code is None and self.pyme_id is None:
            raise ValueError("Elige la pyme a la que quieres cotizar")
        return self


class PortalExtractIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    pyme_id: uuid.UUID | None = Field(
        default=None, description="Pyme cuyos productos se usan; por defecto la de la sesión"
    )


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    yield_unit: BaseUnit


class RequestCreate(BaseModel):
    pyme_id: uuid.UUID | None = Field(default=None, description="Pyme a la que se cotiza; por defecto la de la sesión")
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
    pyme_id: uuid.UUID
    pyme_name: str
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
    pyme_id: uuid.UUID
    pyme_name: str
    status: OrderStatus
    created_at: datetime
    submitted_at: datetime | None
    event_date: date | None
    products: str
    total_clp: int | None

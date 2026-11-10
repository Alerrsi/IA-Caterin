"""Portal de clientes (ADR-007): el cliente final cotiza con el mismo motor que la dueña, guarda sus
cotizaciones y las envía a la pyme, que las acepta o rechaza.

Reglas:
- El cliente solo ve lo suyo: cada consulta filtra por `customer_user_id` (además del filtro de tenant).
- Solo ve precios al cliente: nunca costos, margen, insumos, proveedores ni stock.
- El precio lo calcula `quotes.service.create_quote` (código determinista, ADR-002) con el margen de la pyme.
- Mientras no lo envía, el pedido queda en `customer_draft` y la pyme no lo ve.
"""

import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.security import hash_password
from app.core.tenancy import CurrentUser
from app.core.units import format_decimal
from app.db.enums import DataDomain, OrderStatus, Role
from app.db.models import Order, Pyme, Quote, Recipe, User
from app.modules.portal.schemas import (
    CustomerQuoteOut,
    CustomerQuoteProduct,
    CustomerRegisterIn,
    PendingReason,
    ProductOut,
    RequestCreate,
    RequestLineOut,
    RequestOut,
    RequestSummary,
)
from app.modules.quotes import service as quotes
from app.modules.quotes.schemas import QuoteCreate

CANCELLABLE = (OrderStatus.CUSTOMER_DRAFT, OrderStatus.REQUESTED)
# Errores del cálculo que no impiden guardar la solicitud: la pyme pone el precio al recibirla.
PRICE_LATER = {"margin_required", "quote_calculation"}


# --------------------------------------------------------------------------- registro


def pyme_by_code(db: Session, code: str) -> Pyme:
    pyme = db.scalar(select(Pyme).where(Pyme.customer_code == code.strip()))
    if pyme is None:
        raise ProblemError(404, "portal_code_not_found", "Ese enlace no es válido", "Pídele a la pyme un enlace nuevo.")
    return pyme


def register_customer(db: Session, data: CustomerRegisterIn) -> User:
    pyme = pyme_by_code(db, data.code)
    taken = db.scalar(select(User.id).where(User.email == data.email).execution_options(skip_tenant_filter=True))
    if taken is not None:
        raise ProblemError(409, "email_taken", "Ese correo ya tiene una cuenta", "Prueba iniciar sesión.")
    user = User(
        pyme_id=pyme.id,
        email=data.email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        role=Role.CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------------- límite de lecturas con LLM

_extract_calls: dict[uuid.UUID, deque[float]] = defaultdict(deque)
_extract_lock = threading.Lock()


def check_extract_quota(user_id: uuid.UUID, now: float | None = None) -> None:
    """Pedidos leídos con el LLM por cliente y hora. En memoria del proceso: alcanza para un servidor con un
    solo proceso (el despliegue del MVP); con varios, cada uno lleva su cuenta (ver ADR-007)."""
    limit = get_settings().portal_extract_per_hour
    now = time.monotonic() if now is None else now
    with _extract_lock:
        calls = _extract_calls[user_id]
        while calls and now - calls[0] > 3600:
            calls.popleft()
        if len(calls) >= limit:
            raise ProblemError(
                429, "too_many_reads", "Ya leímos varios pedidos tuyos en la última hora", "Usa el formulario."
            )
        calls.append(now)


# --------------------------------------------------------------------------- productos y solicitudes


def products(db: Session) -> list[ProductOut]:
    """Productos que se pueden pedir: recetas activas marcadas como producto final (no las preparaciones base)."""
    rows = db.scalars(select(Recipe).where(Recipe.is_active, Recipe.is_final_product).order_by(Recipe.name))
    return [ProductOut(id=r.id, name=r.name, yield_unit=r.yield_unit) for r in rows]


def product_choices(db: Session) -> dict[uuid.UUID, str]:
    return {p.id: p.name for p in products(db)}


def _own(db: Session, user: CurrentUser, order_id: uuid.UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.customer_user_id != user.id:
        raise not_found("request_not_found", "No encontramos esa cotización")
    return order


def _try_quote(db: Session, user: CurrentUser, order: Order, today: date) -> None:
    try:
        quotes.create_quote(db, user, order.id, QuoteCreate(), today)
    except ProblemError as exc:
        if exc.code not in PRICE_LATER:
            raise
        db.rollback()


def create_request(db: Session, user: CurrentUser, data: RequestCreate, today: date) -> Order:
    allowed = product_choices(db)
    if any(line.recipe_id not in allowed for line in data.lines):
        raise ProblemError(422, "product_not_found", "Uno de los productos no está disponible")
    order = Order(
        customer_name=user.full_name,
        customer_contact=user.email,
        customer_user_id=user.id,
        status=OrderStatus.CUSTOMER_DRAFT,
        **data.model_dump(exclude={"lines"}),
    )
    db.add(order)
    db.flush()
    for line in quotes.build_lines(db, data.lines):
        line.pyme_id, line.order_id = order.pyme_id, order.id
        db.add(line)
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(order)
    _try_quote(db, user, order, today)
    return order


def requote(db: Session, user: CurrentUser, order_id: uuid.UUID, today: date) -> Order:
    """Recalcula con los precios de hoy. Solo antes de enviarla: después el precio lo maneja la pyme."""
    order = _own(db, user, order_id)
    if order.status != OrderStatus.CUSTOMER_DRAFT:
        raise ProblemError(409, "already_sent", "Ya la enviaste: la pyme revisa el precio")
    _try_quote(db, user, order, today)
    return _own(db, user, order_id)


def send_request(db: Session, user: CurrentUser, order_id: uuid.UUID) -> Order:
    order = _own(db, user, order_id)
    if order.status != OrderStatus.CUSTOMER_DRAFT:
        raise ProblemError(409, "already_sent", "Esta cotización ya se envió")
    order.status = OrderStatus.REQUESTED
    order.submitted_at = datetime.now(UTC)
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(order)
    return order


def cancel_request(db: Session, user: CurrentUser, order_id: uuid.UUID) -> Order:
    order = _own(db, user, order_id)
    if order.status not in CANCELLABLE:
        raise ProblemError(409, "cannot_cancel", "La pyme ya respondió: para cambiarla, contáctala")
    order.status = OrderStatus.CANCELLED
    bump(db, DataDomain.ORDERS)
    db.commit()
    db.refresh(order)
    return order


def list_requests(db: Session, user: CurrentUser) -> list[RequestSummary]:
    orders = db.scalars(
        select(Order).where(Order.customer_user_id == user.id).order_by(Order.created_at.desc()).limit(100)
    )
    out = []
    for o in orders:
        q = quotes.latest_quote(db, o.id)
        names = ", ".join(_line_name(line.requested_name, line.qty, line.unit) for line in o.lines)
        out.append(
            RequestSummary(
                id=o.id,
                status=o.status,
                created_at=o.created_at,
                submitted_at=o.submitted_at,
                event_date=o.event_date,
                products=names,
                total_clp=int(q.total_clp) if q is not None and q.is_complete else None,
            )
        )
    return out


def get_request(db: Session, user: CurrentUser, order_id: uuid.UUID) -> Order:
    return _own(db, user, order_id)


def _qty(value: Any) -> str:
    return format_decimal(Decimal(str(value)))


def _label(unit: Any, qty: Any) -> str:
    return quotes.unit_label(unit, Decimal(str(qty)))


def _line_name(name: str, qty: Any, unit: Any) -> str:
    return f"{_qty(qty)} {_label(unit, qty)} de {name}"


def customer_quote(quote: Quote) -> CustomerQuoteOut:
    """Solo precio al cliente: de `assumptions.products` se toman nombre, cantidad, precio y subtotal."""
    complete = quote.is_complete
    products_out = [
        CustomerQuoteProduct(
            name=p["recipe_name"],
            qty=_qty(p["qty"]),
            unit_label=p["unit_label"],
            unit_price_clp=p["unit_price_clp"] if complete else None,
            subtotal_clp=p["subtotal_clp"] if complete else None,
        )
        for p in quote.assumptions["products"]
    ]
    return CustomerQuoteOut(
        version=quote.version,
        is_complete=complete,
        products=products_out,
        net_clp=int(quote.net_clp) if complete else None,
        vat_pct=format_decimal(Decimal(quote.assumptions["vat_pct"])),
        vat_clp=int(quote.vat_clp) if complete else None,
        total_clp=int(quote.total_clp) if complete else None,
        valid_until=quote.valid_until,
    )


def request_out(db: Session, user: CurrentUser, order: Order) -> RequestOut:
    quote = quotes.latest_quote(db, order.id)
    pending: PendingReason | None = None
    if quote is None:
        pyme = db.get(Pyme, user.pyme_id)
        pending = "margin_required" if pyme is None or pyme.default_margin_pct is None else "cannot_calculate"
    elif not quote.is_complete:
        pending = "missing_prices"
    return RequestOut(
        id=order.id,
        status=order.status,
        created_at=order.created_at,
        submitted_at=order.submitted_at,
        decided_at=order.decided_at,
        event_date=order.event_date,
        guests=order.guests,
        notes=order.notes,
        owner_message=order.owner_message,
        lines=[
            RequestLineOut(
                name=line.requested_name, qty=_qty(line.qty), unit=line.unit, unit_label=_label(line.unit, line.qty)
            )
            for line in order.lines
        ],
        quote=customer_quote(quote) if quote is not None else None,
        price_pending=pending,
        can_send=order.status == OrderStatus.CUSTOMER_DRAFT,
        can_cancel=order.status in CANCELLABLE,
    )


def pdf_quote(db: Session, user: CurrentUser, order_id: uuid.UUID) -> tuple[Quote, Order]:
    order = _own(db, user, order_id)
    quote = quotes.latest_quote(db, order.id)
    if quote is None or not quote.is_complete:
        raise ProblemError(409, "quote_incomplete", "Todavía no hay precio", "La pyme lo revisará al recibirla.")
    return quote, order

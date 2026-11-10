"""Portal de clientes (ADR-007): el cliente final elige una pyme, cotiza con el mismo motor que la dueña, guarda sus
cotizaciones y las envía a esa pyme, que las acepta o rechaza.

Cuentas: un cliente tiene una cuenta (`app_user` con rol `customer`) en cada pyme a la que cotiza, con el mismo
correo y la misma contraseña. Así cada pedido sigue siendo de una sola pyme y el aislamiento entre pymes no cambia.
La cuenta en una pyme nueva se crea sola la primera vez que el cliente le cotiza (si esa pyme tiene el portal abierto).

Reglas:
- El cliente solo ve lo suyo: las consultas filtran por sus cuentas (`customer_user_id`), y lo que escribe en una
  pyme pasa por una sesión de tenant de esa pyme.
- Solo ve precios al cliente: nunca costos, margen, insumos, proveedores ni stock.
- El precio lo calcula `quotes.service.create_quote` (código determinista, ADR-002) con el margen de la pyme.
- Mientras no lo envía, el pedido queda en `customer_draft` y la pyme no lo ve.
"""

import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.security import hash_password
from app.core.tenancy import CurrentUser, open_tenant_session
from app.core.units import format_decimal
from app.db.enums import DataDomain, OrderStatus, Role
from app.db.models import Order, Pyme, Quote, Recipe, User
from app.modules.portal.schemas import (
    CustomerQuoteOut,
    CustomerQuoteProduct,
    CustomerRegisterIn,
    PendingReason,
    PortalPymeOut,
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

# `db` en este módulo es una sesión SIN tenant (get_db): toda consulta filtra explícitamente por las cuentas del
# cliente o por la pyme elegida. Las escrituras se hacen en una sesión de tenant de esa pyme (`_tenant`).


@contextmanager
def _tenant(account: CurrentUser) -> Iterator[Session]:
    session = open_tenant_session(account.pyme_id, account.id)
    try:
        yield session
    finally:
        session.close()


def _cu(user: User) -> CurrentUser:
    return CurrentUser(user.id, user.pyme_id, user.role, user.email, user.full_name)


# --------------------------------------------------------------------------- pymes y cuentas


def accounts(db: Session, me: CurrentUser) -> dict[uuid.UUID, CurrentUser]:
    """Las cuentas activas del cliente, por pyme (mismo correo)."""
    rows = db.scalars(select(User).where(User.email == me.email, User.role == Role.CUSTOMER, User.is_active))
    return {u.pyme_id: _cu(u) for u in rows}


def directory(db: Session, me: CurrentUser | None = None) -> list[PortalPymeOut]:
    """Pymes a las que se puede cotizar: las con el portal abierto y, para un cliente, también las que ya usa."""
    joined = set(accounts(db, me)) if me else set()
    cond: ColumnElement[bool] = Pyme.customer_code.is_not(None)
    if joined:
        cond = or_(cond, Pyme.id.in_(joined))
    rows = db.scalars(select(Pyme).where(cond).order_by(Pyme.name))
    return [PortalPymeOut(id=p.id, name=p.name, commune=p.commune, joined=p.id in joined) for p in rows]


def _pyme_for(db: Session, me: CurrentUser, pyme_id: uuid.UUID | None) -> Pyme:
    pid = pyme_id or me.pyme_id
    pyme = db.get(Pyme, pid)
    if pyme is None or (pyme.customer_code is None and pid not in accounts(db, me)):
        raise ProblemError(404, "pyme_not_available", "Esa pyme no recibe cotizaciones en línea")
    return pyme


def account_in(db: Session, me: CurrentUser, pyme_id: uuid.UUID | None) -> CurrentUser:
    """La cuenta del cliente en esa pyme; la crea (mismo correo y contraseña) si es la primera vez que le cotiza."""
    pyme = _pyme_for(db, me, pyme_id)
    mine = accounts(db, me)
    if pyme.id in mine:
        return mine[pyme.id]
    source = db.get(User, me.id)
    if source is None:  # pragma: no cover - la sesión ya validó la cuenta
        raise not_found("user_not_found")
    user = User(
        pyme_id=pyme.id,
        email=source.email,
        full_name=source.full_name,
        password_hash=source.password_hash,
        role=Role.CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _cu(user)


# --------------------------------------------------------------------------- registro


def pyme_by_code(db: Session, code: str) -> Pyme:
    pyme = db.scalar(select(Pyme).where(Pyme.customer_code == code.strip()))
    if pyme is None:
        raise ProblemError(404, "portal_code_not_found", "Ese enlace no es válido", "Pídele a la pyme un enlace nuevo.")
    return pyme


def register_customer(db: Session, data: CustomerRegisterIn) -> User:
    if data.code:
        pyme = pyme_by_code(db, data.code)
    else:
        found = db.get(Pyme, data.pyme_id)
        if found is None or found.customer_code is None:
            raise ProblemError(404, "pyme_not_available", "Esa pyme no recibe cotizaciones en línea")
        pyme = found
    existing = db.scalar(select(User.role).where(User.email == data.email).limit(1))
    if existing == Role.CUSTOMER:
        raise ProblemError(
            409, "email_taken", "Ya tienes una cuenta de cliente", "Inicia sesión: desde ahí eliges a qué pyme cotizar."
        )
    if existing is not None:
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

_extract_calls: dict[str, deque[float]] = defaultdict(deque)
_extract_lock = threading.Lock()


def check_extract_quota(key: uuid.UUID | str, now: float | None = None) -> None:
    """Pedidos leídos con el LLM por cliente (correo) y hora. En memoria del proceso: alcanza para un servidor con un
    solo proceso (el despliegue del MVP); con varios, cada uno lleva su cuenta (ver ADR-007)."""
    limit = get_settings().portal_extract_per_hour
    now = time.monotonic() if now is None else now
    with _extract_lock:
        calls = _extract_calls[str(key)]
        while calls and now - calls[0] > 3600:
            calls.popleft()
        if len(calls) >= limit:
            raise ProblemError(
                429, "too_many_reads", "Ya leímos varios pedidos tuyos en la última hora", "Usa el formulario."
            )
        calls.append(now)


# --------------------------------------------------------------------------- productos y solicitudes


def products(db: Session, me: CurrentUser, pyme_id: uuid.UUID | None) -> list[ProductOut]:
    """Productos que se pueden pedir a esa pyme: recetas activas marcadas como producto final (no las bases)."""
    pyme = _pyme_for(db, me, pyme_id)
    rows = db.scalars(
        select(Recipe).where(Recipe.pyme_id == pyme.id, Recipe.is_active, Recipe.is_final_product).order_by(Recipe.name)
    )
    return [ProductOut(id=r.id, name=r.name, yield_unit=r.yield_unit) for r in rows]


def product_choices(db: Session, me: CurrentUser, pyme_id: uuid.UUID | None) -> dict[uuid.UUID, str]:
    return {p.id: p.name for p in products(db, me, pyme_id)}


def _locate(db: Session, me: CurrentUser, order_id: uuid.UUID) -> tuple[Order, CurrentUser]:
    """El pedido y la cuenta del cliente en su pyme. 404 si no es de ninguna de sus cuentas."""
    mine = accounts(db, me)
    order = db.get(Order, order_id)
    if order is None or order.pyme_id not in mine or order.customer_user_id != mine[order.pyme_id].id:
        raise not_found("request_not_found", "No encontramos esa cotización")
    return order, mine[order.pyme_id]


def _try_quote(db: Session, account: CurrentUser, order_id: uuid.UUID, today: date) -> None:
    try:
        quotes.create_quote(db, account, order_id, QuoteCreate(), today)
    except ProblemError as exc:
        if exc.code not in PRICE_LATER:
            raise
        db.rollback()


def create_request(db: Session, me: CurrentUser, data: RequestCreate, today: date) -> uuid.UUID:
    allowed = product_choices(db, me, data.pyme_id)
    if any(line.recipe_id not in allowed for line in data.lines):
        raise ProblemError(422, "product_not_found", "Uno de los productos no está disponible en esa pyme")
    account = account_in(db, me, data.pyme_id)
    with _tenant(account) as t:
        order = Order(
            customer_name=account.full_name,
            customer_contact=account.email,
            customer_user_id=account.id,
            status=OrderStatus.CUSTOMER_DRAFT,
            **data.model_dump(exclude={"lines", "pyme_id"}),
        )
        t.add(order)
        t.flush()
        for line in quotes.build_lines(t, data.lines):
            line.pyme_id, line.order_id = order.pyme_id, order.id
            t.add(line)
        bump(t, DataDomain.ORDERS)
        t.commit()
        order_id = order.id
        _try_quote(t, account, order_id, today)
    return order_id


def requote(db: Session, me: CurrentUser, order_id: uuid.UUID, today: date) -> uuid.UUID:
    """Recalcula con los precios de hoy. Solo antes de enviarla: después el precio lo maneja la pyme."""
    order, account = _locate(db, me, order_id)
    if order.status != OrderStatus.CUSTOMER_DRAFT:
        raise ProblemError(409, "already_sent", "Ya la enviaste: la pyme revisa el precio")
    with _tenant(account) as t:
        _try_quote(t, account, order_id, today)
    return order_id


def _set_status(db: Session, me: CurrentUser, order_id: uuid.UUID, allowed: tuple[OrderStatus, ...],
                new: OrderStatus, error: ProblemError) -> uuid.UUID:  # fmt: skip
    order, account = _locate(db, me, order_id)
    if order.status not in allowed:
        raise error
    with _tenant(account) as t:
        row = t.get(Order, order_id)
        assert row is not None  # noqa: S101 - _locate ya lo encontró
        row.status = new
        if new == OrderStatus.REQUESTED:
            row.submitted_at = datetime.now(UTC)
        bump(t, DataDomain.ORDERS)
        t.commit()
    return order_id


def send_request(db: Session, me: CurrentUser, order_id: uuid.UUID) -> uuid.UUID:
    error = ProblemError(409, "already_sent", "Esta cotización ya se envió")
    return _set_status(db, me, order_id, (OrderStatus.CUSTOMER_DRAFT,), OrderStatus.REQUESTED, error)


def cancel_request(db: Session, me: CurrentUser, order_id: uuid.UUID) -> uuid.UUID:
    error = ProblemError(409, "cannot_cancel", "La pyme ya respondió: para cambiarla, contáctala")
    return _set_status(db, me, order_id, CANCELLABLE, OrderStatus.CANCELLED, error)


def list_requests(db: Session, me: CurrentUser) -> list[RequestSummary]:
    mine = accounts(db, me)
    if not mine:
        return []
    names = dict(db.execute(select(Pyme.id, Pyme.name).where(Pyme.id.in_(mine))).all())
    orders = db.scalars(
        select(Order)
        .where(Order.customer_user_id.in_([a.id for a in mine.values()]))
        .order_by(Order.created_at.desc())
        .limit(100)
    )
    out = []
    for o in orders:
        q = quotes.latest_quote(db, o.id)
        out.append(
            RequestSummary(
                id=o.id,
                pyme_id=o.pyme_id,
                pyme_name=names.get(o.pyme_id, ""),
                status=o.status,
                created_at=o.created_at,
                submitted_at=o.submitted_at,
                event_date=o.event_date,
                products=", ".join(_line_name(line.requested_name, line.qty, line.unit) for line in o.lines),
                total_clp=int(q.total_clp) if q is not None and q.is_complete else None,
            )
        )
    return out


def get_request(db: Session, me: CurrentUser, order_id: uuid.UUID) -> RequestOut:
    db.expire_all()  # lo pudo cambiar una sesión de tenant en esta misma solicitud
    order, _account = _locate(db, me, order_id)
    return request_out(db, order)


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


def request_out(db: Session, order: Order) -> RequestOut:
    quote = quotes.latest_quote(db, order.id)
    pending: PendingReason | None = None
    pyme = db.get(Pyme, order.pyme_id)
    if quote is None:
        pending = "margin_required" if pyme is None or pyme.default_margin_pct is None else "cannot_calculate"
    elif not quote.is_complete:
        pending = "missing_prices"
    return RequestOut(
        id=order.id,
        pyme_id=order.pyme_id,
        pyme_name=pyme.name if pyme else "",
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


def pdf_quote(db: Session, me: CurrentUser, order_id: uuid.UUID) -> tuple[Quote, Order, Pyme]:
    order, _account = _locate(db, me, order_id)
    pyme = db.get(Pyme, order.pyme_id)
    assert pyme is not None  # noqa: S101
    quote = quotes.latest_quote(db, order.id)
    if quote is None or not quote.is_complete:
        raise ProblemError(409, "quote_incomplete", "Todavía no hay precio", "La pyme lo revisará al recibirla.")
    return quote, order, pyme

"""Portal de clientes (ADR-007). Rutas públicas para registrarse con el enlace de la pyme y rutas del cliente
autenticado (`CustomerDep`). Las rutas de la pyme rechazan a los clientes de forma central (`get_current_user`)."""

import uuid
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.llm import LLMProvider, get_llm
from app.core.tenancy import CustomerDB, CustomerDep
from app.db.models import Pyme
from app.db.session import get_db
from app.modules.auth import service as auth
from app.modules.auth.schemas import TokenOut
from app.modules.portal import service
from app.modules.portal.schemas import (
    CustomerRegisterIn,
    PortalPymeOut,
    ProductOut,
    RequestCreate,
    RequestOut,
    RequestSummary,
)
from app.modules.quotes import service as quotes
from app.modules.quotes.schemas import ExtractIn, ExtractionOut

router = APIRouter(prefix="/portal", tags=["portal de clientes"])
DB = Annotated[Session, Depends(get_db)]
LLM = Annotated[LLMProvider, Depends(get_llm)]
TZ = ZoneInfo("America/Santiago")


def _today() -> date:
    return datetime.now(TZ).date()


@router.get("/pymes/{code}", response_model=PortalPymeOut)
def pyme_for_code(code: str, db: DB) -> PortalPymeOut:
    """Público: el nombre de la pyme del enlace, para mostrarlo al registrarse."""
    pyme = service.pyme_by_code(db, code)
    return PortalPymeOut(name=pyme.name, commune=pyme.commune)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: CustomerRegisterIn, response: Response, db: DB) -> TokenOut:
    """Público: crea la cuenta de un cliente de la pyme del enlace y entra."""
    user = service.register_customer(db, data)
    return auth.token_response(db, response, user)


@router.get("/products", response_model=list[ProductOut])
def products(_customer: CustomerDep, db: CustomerDB) -> list[ProductOut]:
    return service.products(db)


@router.post("/extract", response_model=ExtractionOut)
def extract(data: ExtractIn, customer: CustomerDep, db: CustomerDB, llm: LLM) -> ExtractionOut:
    """Lee el pedido escrito, igual que para la pyme. **No guarda nada.** Con límite por hora (429)."""
    service.check_extract_quota(customer.id)
    return quotes.extract(llm, data.text, service.product_choices(db), _today())


@router.get("/requests", response_model=list[RequestSummary])
def list_requests(customer: CustomerDep, db: CustomerDB) -> list[RequestSummary]:
    """Las cotizaciones guardadas del cliente, de la más nueva a la más antigua."""
    return service.list_requests(db, customer)


@router.post("/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(data: RequestCreate, customer: CustomerDep, db: CustomerDB) -> RequestOut:
    """Guarda el pedido y lo cotiza con el margen de la pyme. Sin enviar: la pyme todavía no lo ve."""
    order = service.create_request(db, customer, data, _today())
    return service.request_out(db, customer, order)


@router.get("/requests/{order_id}", response_model=RequestOut)
def get_request(order_id: uuid.UUID, customer: CustomerDep, db: CustomerDB) -> RequestOut:
    return service.request_out(db, customer, service.get_request(db, customer, order_id))


@router.post("/requests/{order_id}/quote", response_model=RequestOut)
def requote(order_id: uuid.UUID, customer: CustomerDep, db: CustomerDB) -> RequestOut:
    """Vuelve a calcular con los precios de hoy (solo antes de enviarla)."""
    return service.request_out(db, customer, service.requote(db, customer, order_id, _today()))


@router.post("/requests/{order_id}/send", response_model=RequestOut)
def send_request(order_id: uuid.UUID, customer: CustomerDep, db: CustomerDB) -> RequestOut:
    """La envía a la pyme: le aparece como solicitud para aceptar o rechazar."""
    return service.request_out(db, customer, service.send_request(db, customer, order_id))


@router.post("/requests/{order_id}/cancel", response_model=RequestOut)
def cancel_request(order_id: uuid.UUID, customer: CustomerDep, db: CustomerDB) -> RequestOut:
    """La anula mientras la pyme no responde."""
    return service.request_out(db, customer, service.cancel_request(db, customer, order_id))


@router.get(
    "/requests/{order_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, 409: {"description": "Todavía sin precio"}},
)
def request_pdf(order_id: uuid.UUID, customer: CustomerDep, db: CustomerDB) -> Response:
    """El mismo PDF que la pyme entrega a sus clientes (sin costos ni insumos)."""
    quote, order = service.pdf_quote(db, customer, order_id)
    pyme = db.get(Pyme, customer.pyme_id)
    assert pyme is not None  # noqa: S101
    content, filename = quotes.pdf(quote, order, pyme)
    return Response(
        content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

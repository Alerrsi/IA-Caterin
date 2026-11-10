"""Portal de clientes (ADR-007). Rutas públicas (directorio de pymes y registro) y rutas del cliente autenticado
(`CustomerDep`), que elige a qué pyme cotizar. Las rutas de la pyme rechazan a los clientes de forma central
(`get_current_user`)."""

import uuid
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.llm import LLMProvider, get_llm
from app.core.tenancy import CustomerDep
from app.db.session import get_db
from app.modules.auth import service as auth
from app.modules.auth.schemas import TokenOut
from app.modules.portal import service
from app.modules.portal.schemas import (
    CustomerRegisterIn,
    PortalExtractIn,
    PortalPymeOut,
    ProductOut,
    RequestCreate,
    RequestOut,
    RequestSummary,
)
from app.modules.quotes import service as quotes
from app.modules.quotes.schemas import ExtractionOut

router = APIRouter(prefix="/portal", tags=["portal de clientes"])
DB = Annotated[Session, Depends(get_db)]
LLM = Annotated[LLMProvider, Depends(get_llm)]
TZ = ZoneInfo("America/Santiago")


def _today() -> date:
    return datetime.now(TZ).date()


@router.get("/directory", response_model=list[PortalPymeOut])
def public_directory(db: DB) -> list[PortalPymeOut]:
    """Público: pymes con el portal abierto (nombre y comuna), para elegir al registrarse."""
    return service.directory(db)


@router.get("/pymes/{code}", response_model=PortalPymeOut)
def pyme_for_code(code: str, db: DB) -> PortalPymeOut:
    """Público: la pyme del enlace, para mostrarla al registrarse."""
    pyme = service.pyme_by_code(db, code)
    return PortalPymeOut(id=pyme.id, name=pyme.name, commune=pyme.commune)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: CustomerRegisterIn, response: Response, db: DB) -> TokenOut:
    """Público: crea la cuenta de cliente (con el enlace de una pyme o eligiéndola del directorio) y entra."""
    user = service.register_customer(db, data)
    return auth.token_response(db, response, user)


@router.get("/pymes", response_model=list[PortalPymeOut])
def my_directory(customer: CustomerDep, db: DB) -> list[PortalPymeOut]:
    """Pymes a las que el cliente puede cotizar: las con portal abierto y las que ya usa (`joined`)."""
    return service.directory(db, customer)


@router.get("/products", response_model=list[ProductOut])
def products(customer: CustomerDep, db: DB, pyme_id: Annotated[uuid.UUID | None, Query()] = None) -> list[ProductOut]:
    """Productos de la pyme elegida (por defecto, la de la sesión)."""
    return service.products(db, customer, pyme_id)


@router.post("/extract", response_model=ExtractionOut)
def extract(data: PortalExtractIn, customer: CustomerDep, db: DB, llm: LLM) -> ExtractionOut:
    """Lee el pedido escrito con los productos de la pyme elegida. **No guarda nada.** Con límite por hora (429)."""
    choices = service.product_choices(db, customer, data.pyme_id)
    service.check_extract_quota(customer.email)
    return quotes.extract(llm, data.text, choices, _today())


@router.get("/requests", response_model=list[RequestSummary])
def list_requests(customer: CustomerDep, db: DB) -> list[RequestSummary]:
    """Las cotizaciones guardadas del cliente en todas sus pymes, de la más nueva a la más antigua."""
    return service.list_requests(db, customer)


@router.post("/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(data: RequestCreate, customer: CustomerDep, db: DB) -> RequestOut:
    """Guarda el pedido para la pyme elegida y lo cotiza con su margen. Sin enviar: la pyme todavía no lo ve."""
    order_id = service.create_request(db, customer, data, _today())
    return service.get_request(db, customer, order_id)


@router.get("/requests/{order_id}", response_model=RequestOut)
def get_request(order_id: uuid.UUID, customer: CustomerDep, db: DB) -> RequestOut:
    return service.get_request(db, customer, order_id)


@router.post("/requests/{order_id}/quote", response_model=RequestOut)
def requote(order_id: uuid.UUID, customer: CustomerDep, db: DB) -> RequestOut:
    """Vuelve a calcular con los precios de hoy (solo antes de enviarla)."""
    return service.get_request(db, customer, service.requote(db, customer, order_id, _today()))


@router.post("/requests/{order_id}/send", response_model=RequestOut)
def send_request(order_id: uuid.UUID, customer: CustomerDep, db: DB) -> RequestOut:
    """La envía a su pyme: le aparece como solicitud para aceptar o rechazar."""
    return service.get_request(db, customer, service.send_request(db, customer, order_id))


@router.post("/requests/{order_id}/cancel", response_model=RequestOut)
def cancel_request(order_id: uuid.UUID, customer: CustomerDep, db: DB) -> RequestOut:
    """La anula mientras la pyme no responde."""
    return service.get_request(db, customer, service.cancel_request(db, customer, order_id))


@router.get(
    "/requests/{order_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, 409: {"description": "Todavía sin precio"}},
)
def request_pdf(order_id: uuid.UUID, customer: CustomerDep, db: DB) -> Response:
    """El mismo PDF que la pyme entrega a sus clientes (sin costos ni insumos)."""
    quote, order, pyme = service.pdf_quote(db, customer, order_id)
    content, filename = quotes.pdf(quote, order, pyme)
    return Response(
        content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.errors import ProblemError
from app.core.llm import LLMProvider, get_llm
from app.core.tenancy import CurrentUserDep, OwnerDep, TenantDB
from app.db.enums import OrderStatus
from app.db.models import Pyme
from app.modules.quotes import service
from app.modules.quotes.extractor import extract_order
from app.modules.quotes.pdf import quote_number, render_quote_pdf
from app.modules.quotes.schemas import (
    ExtractIn,
    ExtractionOut,
    OrderCreate,
    OrderOut,
    OrderUpdate,
    QuoteCreate,
    QuoteOut,
    QuoteStatusUpdate,
    QuoteSummary,
    ShoppingList,
)

router = APIRouter(tags=["pedidos y cotizaciones"])
LLM = Annotated[LLMProvider, Depends(get_llm)]


def _today() -> date:
    return date.today()  # noqa: DTZ011 - fecha local del servidor (America/Santiago en producción)


@router.post("/orders/extract", response_model=ExtractionOut)
def extract(data: ExtractIn, _user: CurrentUserDep, db: TenantDB, llm: LLM) -> ExtractionOut:
    """Lee un pedido escrito (p. ej. un mensaje de WhatsApp) y lo devuelve como tabla editable. **No guarda nada.**

    El LLM solo copia productos y cantidades; las recetas y fechas se resuelven en código.
    Si falla, responde `extraction_failed` o `llm_unavailable` y la interfaz ofrece el formulario.
    """
    return extract_order(llm, data.text, service.recipe_choices(db), _today())


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    _user: CurrentUserDep,
    db: TenantDB,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    upcoming_days: Annotated[int | None, Query(ge=0, le=365)] = None,
) -> list[OrderOut]:
    return [service.order_out(db, o) for o in service.list_orders(db, status_filter, upcoming_days, _today())]


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderCreate, _user: CurrentUserDep, db: TenantDB) -> OrderOut:
    return service.order_out(db, service.create_order(db, data))


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> OrderOut:
    return service.order_out(db, service.get_order(db, order_id))


@router.patch("/orders/{order_id}", response_model=OrderOut)
def update_order(order_id: uuid.UUID, data: OrderUpdate, _user: CurrentUserDep, db: TenantDB) -> OrderOut:
    return service.order_out(db, service.update_order(db, order_id, data))


@router.post("/orders/{order_id}/quotes", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
def create_quote(order_id: uuid.UUID, data: QuoteCreate, owner: OwnerDep, db: TenantDB) -> QuoteOut:
    """Calcula una cotización nueva (versión siguiente) con los precios y el stock de este momento.

    Todo el cálculo es determinista (ADR-002). Guarda la versión de precios, los supuestos y quién la generó.
    """
    return service.quote_out(db, service.create_quote(db, owner, order_id, data, _today()))


@router.get("/orders/{order_id}/quotes", response_model=list[QuoteSummary])
def list_quotes(order_id: uuid.UUID, _owner: OwnerDep, db: TenantDB) -> list[QuoteSummary]:
    return [
        QuoteSummary(
            id=q.id,
            version=q.version,
            status=q.status,
            created_at=q.created_at,
            total_clp=int(q.total_clp),
            is_complete=q.is_complete,
        )
        for q in service.list_quotes(db, order_id)
    ]


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: uuid.UUID, _owner: OwnerDep, db: TenantDB) -> QuoteOut:
    return service.quote_out(db, service.get_quote(db, quote_id))


@router.patch("/quotes/{quote_id}", response_model=QuoteOut)
def update_quote(quote_id: uuid.UUID, data: QuoteStatusUpdate, _owner: OwnerDep, db: TenantDB) -> QuoteOut:
    return service.quote_out(db, service.update_quote_status(db, quote_id, data.status))


@router.get("/quotes/{quote_id}/shopping-list", response_model=ShoppingList)
def shopping_list(quote_id: uuid.UUID, _owner: OwnerDep, db: TenantDB) -> ShoppingList:
    """Lista de compras agrupada por proveedor, con días de despacho."""
    return service.shopping_list(db, service.get_quote(db, quote_id))


@router.get(
    "/quotes/{quote_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, 409: {"description": "Cotización incompleta"}},
)
def quote_pdf(quote_id: uuid.UUID, owner: OwnerDep, db: TenantDB) -> Response:
    """PDF para el cliente final. Solo si la cotización está completa (no se inventan precios faltantes)."""
    quote = service.get_quote(db, quote_id)
    if not quote.is_complete:
        raise ProblemError(
            409,
            "quote_incomplete",
            "La cotización está incompleta",
            service.missing_detail(quote) + ". Agrega el precio y vuelve a calcular.",
        )
    order = service.get_order(db, quote.order_id)
    pyme = db.get(Pyme, owner.pyme_id)
    assert pyme is not None  # noqa: S101
    pdf = render_quote_pdf(quote, order, pyme)
    filename = f"{quote_number(quote)}.pdf"
    return Response(
        pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )

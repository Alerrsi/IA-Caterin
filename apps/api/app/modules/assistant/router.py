import json
from collections.abc import Iterator
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi.responses import StreamingResponse

from app.core.embeddings import EmbeddingProvider, get_embeddings
from app.core.llm import LLMProvider, get_llm
from app.core.tenancy import CurrentUserDep, TenantDB
from app.modules.assistant import service
from app.modules.assistant.schemas import AskIn, AskOut, FeedbackIn, QuickActionOut

router = APIRouter(prefix="/assistant", tags=["asistente"])
LLM = Annotated[LLMProvider, Depends(get_llm)]
Embeddings = Annotated[EmbeddingProvider, Depends(get_embeddings)]
SSE = "text/event-stream"


def _today() -> date:
    return datetime.now(ZoneInfo("America/Santiago")).date()


def _sse(items: Iterator[tuple[str, dict[str, Any]]]) -> Iterator[str]:
    for event, data in items:
        yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post(
    "/ask",
    response_model=AskOut,
    responses={200: {"content": {SSE: {"description": "Eventos meta, delta, replace y done (ver docs/API.md)"}}}},
)
def ask(
    data: AskIn,
    user: CurrentUserDep,
    db: TenantDB,
    llm: LLM,
    emb: Embeddings,
    accept: Annotated[str, Header()] = "application/json",
) -> AskOut | StreamingResponse:
    """Responde con datos reales y su fuente. Determinista primero: nivel 0 sin LLM; el LLM solo redacta
    (nivel 1) o resume documentos citándolos (nivel 2). Con `Accept: text/event-stream` el texto llega en
    *streaming* (SSE); si no, en un solo JSON."""
    if SSE not in accept:
        return service.ask(db, user, data, llm, emb, _today())
    turn = service.plan(db, data, emb, _today())  # los errores (p. ej. 404) salen antes de abrir el stream
    return StreamingResponse(
        _sse(service.events(db, user, data, llm, turn)),
        media_type=SSE,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/quick-actions", response_model=list[QuickActionOut])
def quick_actions(_user: CurrentUserDep) -> list[QuickActionOut]:
    """Botones con las preguntas frecuentes: entran directo al nivel 0, sin reconocer nada."""
    return service.quick_actions()


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(data: FeedbackIn, _user: CurrentUserDep, db: TenantDB) -> Response:
    """👍/👎 de la usuaria sobre una respuesta (sirve para mejorar el catálogo y evaluar la redacción, T10)."""
    service.set_feedback(db, data.interaction_id, data.useful)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from app.core.llm import LLMProvider, get_llm
from app.core.tenancy import CurrentUserDep, TenantDB
from app.modules.assistant import service
from app.modules.assistant.schemas import AskIn, AskOut, QuickActionOut

router = APIRouter(prefix="/assistant", tags=["asistente"])
LLM = Annotated[LLMProvider, Depends(get_llm)]


def _today() -> date:
    return datetime.now(ZoneInfo("America/Santiago")).date()


@router.post("/ask", response_model=AskOut)
def ask(data: AskIn, user: CurrentUserDep, db: TenantDB, llm: LLM) -> AskOut:
    """Responde con datos reales y su fuente. Determinista primero: nivel 0 sin LLM; el LLM solo redacta (nivel 1)."""
    return service.ask(db, user, data, llm, _today())


@router.get("/quick-actions", response_model=list[QuickActionOut])
def quick_actions(_user: CurrentUserDep) -> list[QuickActionOut]:
    """Botones con las preguntas frecuentes: entran directo al nivel 0, sin reconocer nada."""
    return service.quick_actions()

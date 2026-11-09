"""Healthchecks: vida del proceso y disponibilidad de dependencias."""

from typing import Any, Literal

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(prefix="/health", tags=["salud"])

ComponentStatus = Literal["ok", "degraded", "down", "disabled"]


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ComponentReport(BaseModel):
    status: ComponentStatus
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    components: dict[str, ComponentReport]


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse()


def _check_database() -> ComponentReport:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return ComponentReport(status="ok")
    except Exception as exc:  # noqa: BLE001 - se informa, no se propaga
        return ComponentReport(status="down", detail=type(exc).__name__)


def _check_llm() -> ComponentReport:
    settings = get_settings()
    if settings.llm_provider != "ollama":
        return ComponentReport(status="disabled", detail=settings.llm_provider)
    try:
        resp = httpx.get(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=2.0)
        resp.raise_for_status()
        names = {m.get("name") for m in resp.json().get("models", [])}
        if settings.llm_model not in names:
            return ComponentReport(status="degraded", detail=f"falta el modelo {settings.llm_model}")
        return ComponentReport(status="ok")
    except Exception as exc:  # noqa: BLE001
        return ComponentReport(status="degraded", detail=type(exc).__name__)


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
def ready() -> Any:
    """La base de datos es obligatoria. El LLM es opcional: sin él, la API degrada (formulario manual)."""
    components = {"database": _check_database(), "llm": _check_llm()}
    if components["database"].status == "down":
        overall: Literal["ok", "degraded", "down"] = "down"
    elif any(c.status == "degraded" for c in components.values()):
        overall = "degraded"
    else:
        overall = "ok"
    body = ReadyResponse(status=overall, components=components)
    return JSONResponse(body.model_dump(), status_code=503 if overall == "down" else 200)

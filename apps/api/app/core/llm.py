"""Acceso al LLM detrás de una interfaz (AGENTS.md, sección 4; ADR-003).

Ningún módulo llama a Ollama ni a otro proveedor directo: todo pasa por `LLMProvider`.
- `OllamaProvider`: por defecto, `qwen3:4b` local, thinking desactivado, salida JSON con schema.
- `FakeProvider`: para pruebas (respuestas programadas).
- `DisabledProvider`: sin LLM; los módulos degradan (p. ej. formulario manual en F3).
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """El LLM no está configurado, no responde o tardó más que el máximo."""


@dataclass(frozen=True)
class LLMResult:
    content: str
    model: str
    latency_ms: int
    tokens_out: int | None = None
    prompt_ms: int | None = None


class LLMProvider(Protocol):
    name: str

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 300, temperature: float = 0.1
    ) -> LLMResult:
        """Una llamada con salida JSON restringida por `schema`."""
        ...


class OllamaProvider:
    def __init__(self, base_url: str, model: str, timeout_s: float, keep_alive: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.timeout_s = timeout_s
        self.keep_alive = keep_alive

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 300, temperature: float = 0.1
    ) -> LLMResult:
        payload = {
            "model": self.name,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "format": schema,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": 4096},
        }
        start = time.perf_counter()
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s)
            resp.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            raise LLMUnavailableError(type(exc).__name__) from exc
        data = resp.json()
        latency = int((time.perf_counter() - start) * 1000)
        logger.info("llm_call", extra={"model": self.name, "latency_ms": latency, "tokens_out": data.get("eval_count")})
        return LLMResult(
            content=data.get("message", {}).get("content", ""),
            model=self.name,
            latency_ms=latency,
            tokens_out=data.get("eval_count"),
            prompt_ms=int((data.get("prompt_eval_duration") or 0) / 1e6) or None,
        )


@dataclass
class FakeProvider:
    """Devuelve respuestas programadas (texto o función del mensaje del usuario)."""

    responses: list[str | Callable[[str], str]] = field(default_factory=list)
    name: str = "fake-llm"
    calls: list[str] = field(default_factory=list)

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 300, temperature: float = 0.1
    ) -> LLMResult:
        self.calls.append(user)
        if not self.responses:
            raise LLMUnavailableError("sin respuestas programadas")
        nxt = self.responses.pop(0)
        content = nxt(user) if callable(nxt) else nxt
        return LLMResult(content=content, model=self.name, latency_ms=1, tokens_out=len(content) // 4)


class DisabledProvider:
    name = "disabled"

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 300, temperature: float = 0.1
    ) -> LLMResult:
        raise LLMUnavailableError("LLM desactivado por configuración")


@lru_cache
def _default_provider() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "ollama":
        return OllamaProvider(s.ollama_url, s.llm_model, s.llm_timeout_s, s.llm_keep_alive)
    if s.llm_provider == "fake":
        return FakeProvider()
    return DisabledProvider()


def get_llm() -> LLMProvider:
    """Dependencia de FastAPI; en pruebas se reemplaza con `app.dependency_overrides`."""
    return _default_provider()


def parse_json_object(content: str) -> dict[str, Any]:
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Se esperaba un objeto JSON")
    return data

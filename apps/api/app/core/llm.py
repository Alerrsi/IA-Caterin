"""Acceso al LLM detrás de una interfaz (AGENTS.md, sección 4; ADR-003).

Ningún módulo llama a Ollama ni a otro proveedor directo: todo pasa por `LLMProvider`.
- `OllamaProvider`: por defecto, `qwen3:4b` local, thinking desactivado. `chat_json` (salida JSON con schema,
  para extraer) y `chat_stream` (texto en *streaming*, para redactar en los niveles 1 y 2 del asistente).
  `chat_stream` también pide JSON (`{"respuesta": "..."}`) y entrega el valor a medida que llega: medido el
  9-nov-2026 con Ollama 0.40.15, `qwen3:4b` (ficha: thinking por defecto, contexto 262144) escribe su
  razonamiento en inglés dentro del texto aunque se mande `think: false`; la gramática JSON lo impide.
- `FakeProvider`: para pruebas (respuestas programadas).
- `DisabledProvider`: sin LLM; los módulos degradan (p. ej. formulario manual en F3).
"""

import json
import logging
import time
from collections.abc import Callable, Iterator
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


ANSWER_SCHEMA = {"type": "object", "properties": {"respuesta": {"type": "string"}}, "required": ["respuesta"]}
_ESCAPES = {"n": "\n", "t": "\t", "r": "", "b": "", "f": "", "/": "/", "\\": "\\", '"': '"'}


class AnswerFieldDecoder:
    """Saca, a medida que llega, el texto del único campo string de `{"respuesta": "..."}`.

    Recibe trozos arbitrarios (una secuencia de escape puede venir partida) y devuelve solo el texto nuevo.
    """

    def __init__(self) -> None:
        self._state = "key"  # key -> colon -> value -> done
        self._escape = False
        self._unicode: str | None = None

    def feed(self, chunk: str) -> str:
        out: list[str] = []
        for ch in chunk:
            if self._state == "key":
                self._state = "colon" if ch == ":" else "key"
            elif self._state == "colon":
                self._state = "value" if ch == '"' else "colon"
            elif self._state == "value":
                self._value_char(ch, out)
        return "".join(out)

    def _value_char(self, ch: str, out: list[str]) -> None:
        if self._unicode is not None:
            self._unicode += ch
            if len(self._unicode) == 4:
                code = int(self._unicode, 16) if all(c in "0123456789abcdefABCDEF" for c in self._unicode) else 0
                if code and not 0xD800 <= code <= 0xDFFF:  # los pares sustitutos (emojis) se omiten
                    out.append(chr(code))
                self._unicode = None
        elif self._escape:
            self._escape = False
            if ch == "u":
                self._unicode = ""
            else:
                out.append(_ESCAPES.get(ch, ch))
        elif ch == "\\":
            self._escape = True
        elif ch == '"':
            self._state = "done"
        else:
            out.append(ch)


@dataclass
class StreamStats:
    """Lo llena `chat_stream` al terminar (si el consumidor corta antes, `tokens_out` queda en None)."""

    model: str = ""
    tokens_out: int | None = None
    prompt_ms: int | None = None


class LLMProvider(Protocol):
    name: str

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 300, temperature: float = 0.1
    ) -> LLMResult:
        """Una llamada con salida JSON restringida por `schema`."""
        ...

    def chat_stream(
        self, system: str, user: str, stats: StreamStats, *, num_predict: int = 120, temperature: float = 0.2
    ) -> Iterator[str]:
        """Una llamada en texto; entrega los trozos a medida que llegan. Lanza `LLMUnavailableError`."""
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

    def chat_stream(
        self, system: str, user: str, stats: StreamStats, *, num_predict: int = 120, temperature: float = 0.2
    ) -> Iterator[str]:
        payload = {
            "model": self.name,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": True,
            "think": False,
            "format": ANSWER_SCHEMA,  # ver el docstring del módulo: evita que el razonamiento se cuele
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": 4096},
        }
        stats.model = self.name
        decoder = AnswerFieldDecoder()
        start = time.perf_counter()
        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_s) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if piece := decoder.feed(data.get("message", {}).get("content", "")):
                        yield piece
                    if data.get("done"):
                        stats.tokens_out = data.get("eval_count")
                        stats.prompt_ms = int((data.get("prompt_eval_duration") or 0) / 1e6) or None
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise LLMUnavailableError(type(exc).__name__) from exc
        latency = int((time.perf_counter() - start) * 1000)
        logger.info("llm_stream", extra={"model": self.name, "latency_ms": latency, "tokens_out": stats.tokens_out})


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

    def chat_stream(
        self, system: str, user: str, stats: StreamStats, *, num_predict: int = 120, temperature: float = 0.2
    ) -> Iterator[str]:
        """Entrega la respuesta programada palabra por palabra (con su espacio), como llegaría de Ollama."""
        self.calls.append(user)
        stats.model = self.name
        if not self.responses:
            raise LLMUnavailableError("sin respuestas programadas")
        nxt = self.responses.pop(0)
        content = nxt(user) if callable(nxt) else nxt
        words = content.split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else word + " "
        stats.tokens_out = len(words)


class DisabledProvider:
    name = "disabled"

    def chat_json(
        self, system: str, user: str, schema: dict[str, Any], *, num_predict: int = 300, temperature: float = 0.1
    ) -> LLMResult:
        raise LLMUnavailableError("LLM desactivado por configuración")

    def chat_stream(
        self, system: str, user: str, stats: StreamStats, *, num_predict: int = 120, temperature: float = 0.2
    ) -> Iterator[str]:
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

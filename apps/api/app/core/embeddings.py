"""Embeddings detrás de una interfaz (ADR-003, ADR-005).

- `OllamaEmbeddings`: por defecto `bge-m3` (1024 dimensiones) servido por Ollama.
- `FakeEmbeddings`: determinista para pruebas (trigramas de caracteres con *hashing*); no es semántico.
- `DisabledEmbeddings`: sin embeddings; el enrutador usa solo reglas y la búsqueda solo texto completo.

Todos los vectores salen normalizados (norma 1): el coseno es el producto punto.
"""

import hashlib
import logging
import math
import time
import unicodedata
from functools import lru_cache
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.db.models import EMBEDDING_DIM

logger = logging.getLogger(__name__)


class EmbeddingsUnavailableError(RuntimeError):
    """El servicio de embeddings no está configurado o no responde."""


class EmbeddingProvider(Protocol):
    name: str
    version: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class OllamaEmbeddings:
    def __init__(self, base_url: str, model: str, version: str, timeout_s: float, keep_alive: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.name = model
        self.version = version
        self.timeout_s = timeout_s
        self.keep_alive = keep_alive

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        start = time.perf_counter()
        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.name, "input": texts, "keep_alive": self.keep_alive},
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            vectors: list[list[float]] = resp.json()["embeddings"]
        except (httpx.HTTPError, OSError, KeyError, ValueError) as exc:
            raise EmbeddingsUnavailableError(type(exc).__name__) from exc
        if any(len(v) != EMBEDDING_DIM for v in vectors):
            raise EmbeddingsUnavailableError(f"dimensión distinta de {EMBEDDING_DIM}")
        logger.debug("embed", extra={"n": len(texts), "ms": int((time.perf_counter() - start) * 1000)})
        return [_normalize(v) for v in vectors]


class FakeEmbeddings:
    """Bolsa de trigramas con *hashing*: frases con palabras en común quedan cerca. Solo para pruebas."""

    name = "fake-embeddings"
    version = "fake-1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            plain = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
            vec = [0.0] * EMBEDDING_DIM
            for word in plain.split():
                padded = f" {word} "
                for i in range(len(padded) - 2):
                    h = int(hashlib.md5(padded[i : i + 3].encode(), usedforsecurity=False).hexdigest()[:8], 16)
                    vec[h % EMBEDDING_DIM] += 1.0
            out.append(_normalize(vec))
        return out


class DisabledEmbeddings:
    name = "disabled"
    version = "disabled"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingsUnavailableError("embeddings desactivados por configuración")


@lru_cache
def _default() -> EmbeddingProvider:
    s = get_settings()
    if s.embeddings_provider == "ollama":
        return OllamaEmbeddings(
            s.ollama_url, s.embedding_model, s.embedding_version, s.embedding_timeout_s, s.llm_keep_alive
        )
    if s.embeddings_provider == "fake":
        return FakeEmbeddings()
    return DisabledEmbeddings()


def get_embeddings() -> EmbeddingProvider:
    """Dependencia de FastAPI; en pruebas se reemplaza con `app.dependency_overrides`."""
    return _default()


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))

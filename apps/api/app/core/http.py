"""Helpers HTTP comunes: paginación por cursor, ETag e Idempotency-Key (docs/API.md, sección 3)."""

import base64
import hashlib
import json
import uuid
from typing import Annotated, Any

from fastapi import Header, Query, Request, Response
from pydantic import BaseModel

from app.core.errors import ProblemError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


LimitQuery = Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Cantidad de resultados (máx. 100)")]
CursorQuery = Annotated[str | None, Query(description="Cursor opaco de la página anterior")]


def encode_cursor(values: list[Any]) -> str:
    raw = json.dumps(values, default=str, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> list[Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        values = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ProblemError(400, "invalid_cursor", "El cursor de paginación no es válido") from exc
    if not isinstance(values, list):
        raise ProblemError(400, "invalid_cursor", "El cursor de paginación no es válido")
    return values


def etag_json(request: Request, model: BaseModel, status_code: int = 200) -> Response:
    """Responde JSON con ETag débil; si el cliente ya tiene esa versión, responde 304 sin cuerpo."""
    body = model.model_dump_json().encode()
    etag = f'W/"{hashlib.sha256(body).hexdigest()[:20]}"'
    headers = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if etag in [t.strip() for t in request.headers.get("if-none-match", "").split(",")]:
        return Response(status_code=304, headers=headers)
    return Response(body, status_code=status_code, media_type="application/json", headers=headers)


def idempotency_key(
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", description="UUID para reintentos seguros desde la cola offline")
    ] = None,
) -> uuid.UUID | None:
    if idempotency_key is None:
        return None
    try:
        return uuid.UUID(idempotency_key)
    except ValueError as exc:
        raise ProblemError(400, "invalid_idempotency_key", "La clave de idempotencia debe ser un UUID") from exc

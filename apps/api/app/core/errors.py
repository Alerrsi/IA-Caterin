"""Errores en formato único RFC 9457 (problem details), con textos en español de Chile."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"

_DEFAULT_TITLES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "La solicitud no es válida"),
    401: ("unauthorized", "Necesitas iniciar sesión"),
    403: ("forbidden", "No tienes permiso para hacer esto"),
    404: ("not_found", "No encontramos lo que buscas"),
    405: ("method_not_allowed", "Esta acción no está permitida aquí"),
    409: ("conflict", "Hay un conflicto con los datos actuales"),
    413: ("payload_too_large", "El archivo es demasiado grande"),
    415: ("unsupported_media_type", "Este tipo de archivo no está permitido"),
    422: ("validation_error", "Revisa los datos ingresados"),
    429: ("too_many_requests", "Demasiados intentos, espera un momento"),
    500: ("internal_error", "Algo salió mal de nuestro lado"),
    503: ("service_unavailable", "El servicio no está disponible por ahora"),
}

_VALIDATION_MESSAGES: dict[str, str] = {
    "missing": "Este campo es obligatorio",
    "string_too_short": "El texto es demasiado corto (mínimo {min_length} caracteres)",
    "string_too_long": "El texto es demasiado largo (máximo {max_length} caracteres)",
    "greater_than": "Debe ser mayor que {gt}",
    "greater_than_equal": "Debe ser mayor o igual que {ge}",
    "less_than_equal": "Debe ser menor o igual que {le}",
    "int_parsing": "Debe ser un número entero",
    "decimal_parsing": "Debe ser un número",
    "float_parsing": "Debe ser un número",
    "enum": "Valor no permitido",
    "literal_error": "Valor no permitido",
    "value_error": "Valor no válido",
    "uuid_parsing": "Identificador no válido",
    "date_from_datetime_parsing": "Fecha no válida",
    "date_parsing": "Fecha no válida",
    "json_invalid": "El JSON no es válido",
}


class ProblemError(Exception):
    """Error de negocio que se responde como problem details."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str | None = None,
        errors: list[dict[str, str]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.errors = errors
        self.extra = extra or {}


def not_found(code: str, title: str = "No encontramos lo que buscas") -> ProblemError:
    return ProblemError(404, code, title)


def problem_response(
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    errors: list[dict[str, str]] | None = None,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:caterin:problem:{code}",
        "title": title,
        "status": status,
        "code": code,
        "instance": request.url.path,
        "request_id": get_request_id(),
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    body.update(extra or {})
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def _validation_message(err: dict[str, Any]) -> str:
    template = _VALIDATION_MESSAGES.get(str(err.get("type")), "Valor no válido")
    try:
        return template.format(**(err.get("ctx") or {}))
    except (KeyError, IndexError):
        return template


def _field_name(loc: tuple[Any, ...] | list[Any]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


async def _problem_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ProblemError):  # pragma: no cover - Starlette garantiza el tipo
        raise exc
    return problem_response(request, exc.status, exc.code, exc.title, exc.detail, exc.errors, exc.extra)


async def _http_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover - Starlette garantiza el tipo
        raise exc
    code, title = _DEFAULT_TITLES.get(exc.status_code, ("error", "Ocurrió un error"))
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail not in ("Not Found",) else None
    return problem_response(request, exc.status_code, code, title, detail, headers=getattr(exc, "headers", None))


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover - Starlette garantiza el tipo
        raise exc
    errors = [{"field": _field_name(e.get("loc", ())), "message": _validation_message(e)} for e in exc.errors()]
    code, title = _DEFAULT_TITLES[422]
    return problem_response(request, 422, code, title, errors=errors)


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", extra={"path": request.url.path})
    code, title = _DEFAULT_TITLES[500]
    return problem_response(request, 500, code, title, "Intenta de nuevo en unos minutos.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemError, _problem_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _unhandled_handler)

"""Punto de entrada de la API de Cáterin."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestIdMiddleware
from app.modules.auth.router import router as auth_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="Cáterin API",
        version=__version__,
        description="Gestión con IA para pymes de catering de La Araucanía.",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "ETag"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health_router)
    api.include_router(auth_router)
    app.include_router(api)
    return app


app = create_app()

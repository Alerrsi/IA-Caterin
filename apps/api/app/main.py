"""Punto de entrada de la API de Cáterin."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestIdMiddleware
from app.modules.assistant.router import router as assistant_router
from app.modules.auth.router import router as auth_router
from app.modules.imports.router import router as imports_router
from app.modules.inventory.router import router as inventory_router
from app.modules.quotes.router import router as quotes_router
from app.modules.recipes.router import router as recipes_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.vision.detector import load_detector
from app.modules.vision.router import router as vision_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    load_detector()  # carga el ONNX al iniciar: la primera foto no paga la carga (si no hay modelo, solo avisa)
    yield


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
        lifespan=lifespan,
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
    for router in (
        auth_router,
        inventory_router,
        suppliers_router,
        recipes_router,
        imports_router,
        quotes_router,
        vision_router,
        assistant_router,
    ):
        api.include_router(router)
    app.include_router(api)
    return app


app = create_app()

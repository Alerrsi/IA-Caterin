"""Motor y sesiones de SQLAlchemy (síncrono; FastAPI corre las rutas sync en un threadpool)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    """Sesión sin filtro de tenant. Solo para auth y salud; el resto usa core.tenancy."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()

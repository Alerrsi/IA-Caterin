"""Configuración común de pruebas.

Las pruebas de integración usan un Postgres real (base `caterin_test`), nunca la base de desarrollo.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_test"
)
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDINGS_PROVIDER"] = "fake"  # nunca llamar a Ollama desde las pruebas
os.environ["REFRESH_COOKIE_SECURE"] = "false"  # TestClient usa http

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(migrated_db: None) -> Iterator[TestClient]:
    try:
        with TestClient(create_app()) as c:
            yield c
    finally:
        truncate_all()


# --------------------------------------------------------------------------- base de datos de pruebas

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402


def alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = os.environ["DATABASE_URL"]
    return cfg


@pytest.fixture(scope="session")
def migrated_db() -> None:
    command.upgrade(alembic_config(), "head")


def truncate_all() -> None:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(migrated_db: None) -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        truncate_all()

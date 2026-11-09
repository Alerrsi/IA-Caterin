"""Configuración común de pruebas.

Las pruebas de integración usan un Postgres real (base `caterin_test`), nunca la base de desarrollo.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://caterin:caterin_dev@postgres:5432/caterin_test"
)
os.environ["LLM_PROVIDER"] = "fake"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c

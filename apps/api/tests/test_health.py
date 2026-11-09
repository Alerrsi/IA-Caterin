import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.api import health


def test_live(client: TestClient) -> None:
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_with_database(client: TestClient) -> None:
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["components"]["database"]["status"] == "ok"
    assert body["components"]["llm"]["status"] == "disabled"  # LLM_PROVIDER=fake en pruebas


def test_ready_reports_database_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = create_engine("postgresql+psycopg://x:y@127.0.0.1:1/nada", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(health, "get_engine", lambda: bad)
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 503
    assert resp.json()["components"]["database"]["status"] == "down"

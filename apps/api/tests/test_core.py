import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.errors import ProblemError, register_error_handlers
from app.core.request_context import RequestIdMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    router = APIRouter()

    class Body(BaseModel):
        qty: int = Field(gt=0)
        name: str

    @router.post("/items")
    def create(body: Body) -> dict[str, str]:
        return {"name": body.name}

    @router.get("/boom")
    def boom() -> None:
        raise ProblemError(409, "duplicated", "Ya existe", "Prueba con otro nombre.")

    @router.get("/crash")
    def crash() -> None:
        raise RuntimeError("secreto interno")

    app.include_router(router)
    return app


def test_validation_error_is_problem_json_in_spanish() -> None:
    client = TestClient(_app())
    resp = client.post("/items", json={"qty": 0})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "validation_error"
    assert body["request_id"]
    fields = {e["field"]: e["message"] for e in body["errors"]}
    assert fields == {"qty": "Debe ser mayor que 0", "name": "Este campo es obligatorio"}


def test_problem_error_and_not_found() -> None:
    client = TestClient(_app())
    resp = client.get("/boom")
    assert resp.status_code == 409
    assert resp.json()["title"] == "Ya existe"
    assert resp.json()["detail"] == "Prueba con otro nombre."
    resp = client.get("/no-existe")
    assert resp.status_code == 404
    assert resp.json()["title"] == "No encontramos lo que buscas"


def test_unhandled_error_does_not_leak_details() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/crash")
    assert resp.status_code == 500
    assert "secreto" not in resp.text


def test_request_id_header_is_returned() -> None:
    client = TestClient(_app())
    resp = client.get("/boom", headers={"X-Request-ID": "abc123"})
    assert resp.headers["x-request-id"] == "abc123"
    assert resp.json()["request_id"] == "abc123"


def test_settings_defaults_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_S", "12.5")
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.cl"]')
    s = Settings()
    assert s.llm_timeout_s == 12.5
    assert s.cors_origins == ["https://a.cl"]
    assert s.jwt_access_ttl_min == 15


def test_answer_field_decoder_handles_split_escapes() -> None:
    from app.core.llm import AnswerFieldDecoder

    raw = '{\n  "respuesta": "Cuesta $9.156 \\"con IVA\\".\\nOjo: ma\\u00f1ana"\n}'
    for size in (1, 2, 3, 7, len(raw)):
        dec = AnswerFieldDecoder()
        text = "".join(dec.feed(raw[i : i + size]) for i in range(0, len(raw), size))
        assert text == 'Cuesta $9.156 "con IVA".\nOjo: mañana'
    assert AnswerFieldDecoder().feed('{"respuesta": "a"} basura "b"') == "a"

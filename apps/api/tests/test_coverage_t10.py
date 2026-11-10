"""T10: pruebas para las ramas sin cubrir que importan (proveedores HTTP de LLM y embeddings, salud, la puntuación
del evaluador del extractor y el verificador de cifras). Todo con HTTP simulado: nunca llaman a Ollama."""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import health
from app.core import embeddings as emb_mod
from app.core import llm as llm_mod
from app.core.config import get_settings
from app.core.embeddings import (
    DisabledEmbeddings,
    EmbeddingsUnavailableError,
    FakeEmbeddings,
    OllamaEmbeddings,
)
from app.core.llm import (
    DisabledProvider,
    FakeProvider,
    LLMUnavailableError,
    OllamaProvider,
    StreamStats,
    parse_json_object,
)
from app.db.models import EMBEDDING_DIM
from app.db.seed import AROMOS
from app.modules.assistant.verifier import figures_ok, numbers
from app.modules.quotes.evaluation import _pct, _total, evaluate_case

# --------------------------------------------------------------------------- utilidades


def _response(status: int, body: Any) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "http://ollama/api"))


# --------------------------------------------------------------------------- LLM: chat_json con Ollama


def test_ollama_chat_json_sends_schema_without_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        sent.update(url=url, payload=json, timeout=timeout)
        return _response(
            200,
            {"message": {"content": '{"a": 1}'}, "eval_count": 7, "prompt_eval_duration": 1_250_000_000},
        )

    monkeypatch.setattr(llm_mod.httpx, "post", fake_post)
    p = OllamaProvider("http://ollama:11434/", "qwen3:4b", 12.0, "30m")
    res = p.chat_json("sis", "usr", {"type": "object"}, num_predict=50, temperature=0.0)
    assert sent["url"] == "http://ollama:11434/api/chat" and sent["timeout"] == 12.0
    payload = sent["payload"]
    assert payload["think"] is False and payload["stream"] is False and payload["format"] == {"type": "object"}
    assert payload["options"] == {"temperature": 0.0, "num_predict": 50, "num_ctx": 4096}
    assert res.content == '{"a": 1}' and res.tokens_out == 7 and res.prompt_ms == 1250 and res.model == "qwen3:4b"


def test_ollama_chat_json_http_error_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_mod.httpx, "post", lambda *a, **k: _response(500, {"error": "boom"}))
    with pytest.raises(LLMUnavailableError, match="HTTPStatusError"):
        OllamaProvider("http://o", "m", 1, "1m").chat_json("s", "u", {})

    def refuse(*a: Any, **k: Any) -> httpx.Response:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(llm_mod.httpx, "post", refuse)
    with pytest.raises(LLMUnavailableError, match="ConnectError"):
        OllamaProvider("http://o", "m", 1, "1m").chat_json("s", "u", {})


# --------------------------------------------------------------------------- LLM: chat_stream con Ollama


class _FakeStream:
    def __init__(self, lines: list[str], status: int = 200) -> None:
        self.lines, self.status_code = lines, status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://o"), response=httpx.Response(500))

    def iter_lines(self) -> Iterator[str]:
        yield from self.lines


def _patch_stream(monkeypatch: pytest.MonkeyPatch, lines: list[str], status: int = 200) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    @contextmanager
    def fake_stream(method: str, url: str, json: dict[str, Any], timeout: float) -> Iterator[_FakeStream]:
        seen.update(method=method, url=url, payload=json)
        yield _FakeStream(lines, status)

    monkeypatch.setattr(llm_mod.httpx, "stream", fake_stream)
    return seen


def test_ollama_stream_decodes_answer_field_split_across_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    # Así llega de Ollama con `format`: el JSON viene partido en trozos arbitrarios (incluso dentro de "ñ").
    chunks = ['{\n  "resp', 'uesta": "La docena', " cuesta $9.156, ma\\u00", "f1ana.", '"\n}']
    lines = [json.dumps({"message": {"content": c}, "done": False}) for c in chunks]
    lines.insert(2, "")  # líneas vacías se ignoran
    lines.append(json.dumps({"message": {"content": ""}, "done": True, "eval_count": 21, "prompt_eval_duration": 9e8}))
    seen = _patch_stream(monkeypatch, lines)
    stats = StreamStats()
    text = "".join(OllamaProvider("http://o/", "qwen3:4b", 5, "30m").chat_stream("s", "u", stats))
    assert text == "La docena cuesta $9.156, mañana."
    assert seen["payload"]["stream"] is True and seen["payload"]["format"] == llm_mod.ANSWER_SCHEMA
    assert stats.model == "qwen3:4b" and stats.tokens_out == 21 and stats.prompt_ms == 900


def test_ollama_stream_errors_are_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_stream(monkeypatch, [], status=500)
    with pytest.raises(LLMUnavailableError):
        list(OllamaProvider("http://o", "m", 1, "1m").chat_stream("s", "u", StreamStats()))
    _patch_stream(monkeypatch, ["{esto no es json"])
    with pytest.raises(LLMUnavailableError, match="JSONDecodeError"):
        list(OllamaProvider("http://o", "m", 1, "1m").chat_stream("s", "u", StreamStats()))


def test_disabled_and_fake_providers() -> None:
    with pytest.raises(LLMUnavailableError):
        DisabledProvider().chat_json("s", "u", {})
    with pytest.raises(LLMUnavailableError):
        list(DisabledProvider().chat_stream("s", "u", StreamStats()))
    fake = FakeProvider(responses=[lambda u: u.upper()])
    assert fake.chat_json("s", "hola", {}).content == "HOLA" and fake.calls == ["hola"]
    with pytest.raises(LLMUnavailableError):
        fake.chat_json("s", "otra", {})  # sin respuestas programadas


def test_default_provider_follows_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, cls in (("ollama", OllamaProvider), ("fake", FakeProvider), ("disabled", DisabledProvider)):
        monkeypatch.setattr(
            llm_mod, "get_settings", lambda n=name: get_settings().model_copy(update={"llm_provider": n})
        )
        llm_mod._default_provider.cache_clear()
        assert isinstance(llm_mod.get_llm(), cls)
    llm_mod._default_provider.cache_clear()


def test_parse_json_object_rejects_non_objects() -> None:
    assert parse_json_object('{"x": 1}') == {"x": 1}
    with pytest.raises(ValueError, match="objeto JSON"):
        parse_json_object("[1, 2]")


# --------------------------------------------------------------------------- embeddings con Ollama


def test_ollama_embeddings_normalize_and_send_keep_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        sent.update(url=url, payload=json)
        return _response(200, {"embeddings": [[3.0, 4.0] + [0.0] * (EMBEDDING_DIM - 2)]})

    monkeypatch.setattr(emb_mod.httpx, "post", fake_post)
    e = OllamaEmbeddings("http://ollama:11434/", "bge-m3", "v1", 3.0, "30m")
    [vec] = e.embed(["harina"])
    assert sent["url"] == "http://ollama:11434/api/embed" and sent["payload"]["keep_alive"] == "30m"
    assert vec[:2] == [0.6, 0.8] and abs(emb_mod.cosine(vec, vec) - 1) < 1e-9
    assert e.embed([]) == []  # sin textos no llama


def test_ollama_embeddings_wrong_dimension_or_error_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    e = OllamaEmbeddings("http://o", "otro-modelo", "v1", 1.0, "1m")
    monkeypatch.setattr(emb_mod.httpx, "post", lambda *a, **k: _response(200, {"embeddings": [[1.0, 2.0]]}))
    with pytest.raises(EmbeddingsUnavailableError, match="dimensión"):
        e.embed(["x"])  # un modelo con otra dimensión no puede mezclarse con la columna vector(1024)
    monkeypatch.setattr(emb_mod.httpx, "post", lambda *a, **k: _response(200, {"sin": "embeddings"}))
    with pytest.raises(EmbeddingsUnavailableError, match="KeyError"):
        e.embed(["x"])
    monkeypatch.setattr(emb_mod.httpx, "post", lambda *a, **k: _response(404, {"error": "model not found"}))
    with pytest.raises(EmbeddingsUnavailableError, match="HTTPStatusError"):
        e.embed(["x"])
    with pytest.raises(EmbeddingsUnavailableError):
        DisabledEmbeddings().embed(["x"])


def test_default_embeddings_follow_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, cls in (("ollama", OllamaEmbeddings), ("fake", FakeEmbeddings), ("disabled", DisabledEmbeddings)):
        upd = {"embeddings_provider": name}
        monkeypatch.setattr(emb_mod, "get_settings", lambda u=upd: get_settings().model_copy(update=u))
        emb_mod._default.cache_clear()
        assert isinstance(emb_mod.get_embeddings(), cls)
    emb_mod._default.cache_clear()


# --------------------------------------------------------------------------- salud del LLM


@pytest.mark.parametrize(
    ("reply", "status", "detail"),
    [
        (_response(200, {"models": [{"name": "qwen3:4b"}, {"name": "bge-m3:latest"}]}), "ok", None),
        (_response(200, {"models": [{"name": "bge-m3:latest"}]}), "degraded", "falta el modelo qwen3:4b"),
        (_response(503, {}), "degraded", "HTTPStatusError"),
    ],
)
def test_ready_reports_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, reply: httpx.Response, status: str, detail: str | None
) -> None:
    on = get_settings().model_copy(update={"llm_provider": "ollama", "llm_model": "qwen3:4b"})
    monkeypatch.setattr(health, "get_settings", lambda: on)
    monkeypatch.setattr(health.httpx, "get", lambda *a, **k: reply)
    body = client.get("/api/v1/health/ready").json()
    assert body["components"]["llm"] == {"status": status, "detail": detail}
    assert body["status"] == ("ok" if status == "ok" else "degraded")  # sin LLM la API degrada, no se cae


# --------------------------------------------------------------------------- evaluador del extractor (T05/T10)

RECIPES = {uuid.uuid4(): r.name for r in AROMOS.recipes}
CASE = {
    "id": "c1",
    "text": "Hola, necesito 80 empanadas de pino y 3 docenas de sopaipillas para el sábado, somos 40",
    "guests": 40,
    "date": "2026-11-14",
    "items": [["Empanadas de pino", "80", "unit"], ["Sopaipillas", "3", "dozen"]],
}


def _llm(items: list[dict[str, Any]], guests: int | None = 40, date_text: str | None = "sábado") -> FakeProvider:
    return FakeProvider(responses=[json.dumps({"items": items, "guests": guests, "event_date_text": date_text})])


def test_evaluate_case_scores_every_field() -> None:
    good = _llm(
        [
            {"name": "empanadas de pino", "quantity": 80, "unit": "unidad"},
            {"name": "sopaipillas", "quantity": 3, "unit": "docena"},
        ]
    )
    r = evaluate_case(good, CASE, RECIPES)
    assert r["exact"] is True and r["fields_ok"] == r["fields_total"] == _total(CASE) == 9
    assert r["failed"] == [] and r["got_date"] == "2026-11-14"


def test_evaluate_case_detects_wrong_qty_extra_product_and_missing_guests() -> None:
    bad = _llm(
        [
            {"name": "empanadas de pino", "quantity": 8, "unit": "unidad"},  # cantidad mal copiada
            {"name": "sopaipillas", "quantity": 3, "unit": "unidad"},  # unidad mal
            {"name": "bebidas", "quantity": 1, "unit": "unidad"},  # producto inventado
        ],
        guests=None,
    )
    r = evaluate_case(bad, CASE, RECIPES)
    assert r["exact"] is False
    assert set(r["failed"]) == {
        "guests",
        "Empanadas de pino: cantidad",
        "Sopaipillas: unidad",
        "sin productos inventados",
    }


def test_evaluate_case_expected_unmatched_and_llm_failure() -> None:
    case = {"id": "c2", "text": "quiero 2 tortas de mil hojas", "guests": None, "date": None,
            "items": [[None, "2", None]]}  # fmt: skip
    r = evaluate_case(
        _llm([{"name": "tortas de mil hojas", "quantity": 2, "unit": "unidad"}], None, None), case, RECIPES
    )
    assert r["exact"] is True  # no existe esa receta: lo correcto es NO asociarla
    down = evaluate_case(FakeProvider(), CASE, RECIPES)  # sin LLM: se cuenta como caso con error, no se cae
    assert down["error"] and down["fields_ok"] == 0 and down["fields_total"] == 9 and down["exact"] is False


def test_percentile_helper() -> None:
    assert _pct([], 0.95) is None
    assert _pct([30, 10, 20], 0.5) == 20 and _pct(list(range(1, 21)), 0.95) == 19


# --------------------------------------------------------------------------- verificador de cifras


def test_verifier_ignores_numbers_it_cannot_read_safely() -> None:
    assert numbers("2,5 kg y $21.000") == {numbers("2,5").pop(), numbers("21000").pop()}
    assert figures_ok("Te quedan 2,5 kg.", "Stock: 2,5 kg")


@pytest.mark.xfail(
    strict=True,
    reason="BUG (T10): números con formato de EE. UU. (1,500,000) no se pueden leer y el verificador los descarta en "
    "silencio, así que una cifra inventada en ese formato pasa la verificación (ADR-002). Debería rechazarse.",
)
def test_verifier_rejects_invented_figure_in_us_format() -> None:
    assert not figures_ok("Te cuesta $1,500,000.", "Producir 12 unidades cuesta $21.000.")

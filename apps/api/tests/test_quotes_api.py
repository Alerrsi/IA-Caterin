"""F3 de punta a punta por la API: extraer -> pedido -> cotización -> lista de compras -> PDF."""

import io
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm import FakeProvider, LLMProvider, OllamaProvider, get_llm
from app.db.enums import MetricKind
from app.db.models import MetricEvent, Order, Recipe
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from tests.helpers import PASSWORD, Tenant, assert_isolated, login, register

API = "/api/v1"


@pytest.fixture
def demo(client: TestClient, db: Session) -> dict[str, object]:
    seed(db)
    owner = login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    recipes = dict(db.execute(select(Recipe.name, Recipe.id)).all())
    return {"owner": owner, "recipes": {k: str(v) for k, v in recipes.items()}, "db": db}


@pytest.fixture
def fake_llm(client: TestClient) -> Iterator[FakeProvider]:
    fake = FakeProvider()
    client.app.dependency_overrides[get_llm] = lambda: fake  # type: ignore[attr-defined]
    yield fake
    client.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def _llm_json(items: list[dict[str, object]], guests: int | None = None, when: str | None = None) -> str:
    return json.dumps({"guests": guests, "event_date_text": when, "items": items})


# --------------------------------------------------------------------------- extracción


def test_extract_resolves_recipes_units_and_dates(client: TestClient, demo: dict, fake_llm: FakeProvider) -> None:  # type: ignore[type-arg]
    fake_llm.responses.append(
        _llm_json(
            [
                {"name": "empanaditas de pino", "quantity": 80, "unit": "unidades"},
                {"name": "brochetas de pollo", "quantity": 4, "unit": "docenas"},
                {"name": "empanadas", "quantity": 2, "unit": "docena"},
            ],
            guests=60,
            when="mañana",
        )
    )
    text = "Hola, necesito 80 empanaditas de pino, 4 docenas de brochetas y 2 docenas de empanadas para mañana"
    resp = client.post(f"{API}/orders/extract", headers=demo["owner"], json={"text": text})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["guests"] == 60
    assert body["event_date"] is not None
    lines = body["lines"]
    assert (lines[0]["recipe_name"], lines[0]["qty"], lines[0]["unit"]) == ("Empanadas de pino", "80", "unit")
    assert (lines[1]["recipe_name"], lines[1]["unit"]) == ("Brochetas de pollo", "dozen")
    assert lines[2]["recipe_id"] is None  # "empanadas" es ambigua: se pregunta
    assert {s["recipe_name"] for s in lines[2]["suggestions"]} >= {"Empanadas de pino", "Empanadas de queso"}
    assert body["needs_review"] is True
    assert body["extraction"]["prompt_version"] == "extract-v1"
    assert "<pedido>" in fake_llm.calls[0]  # el texto va delimitado como dato
    assert client.get(f"{API}/orders", headers=demo["owner"]).json()  # extraer no creó pedidos nuevos


def test_extract_flags_quantities_not_in_text(client: TestClient, demo: dict, fake_llm: FakeProvider) -> None:  # type: ignore[type-arg]
    fake_llm.responses.append(_llm_json([{"name": "brochetas de pollo", "quantity": 201, "unit": "unidad"}]))
    body = client.post(f"{API}/orders/extract", headers=demo["owner"], json={"text": "200 brochetas de pollo"}).json()
    assert body["lines"][0]["warning"].startswith("Revisa la cantidad")
    assert body["needs_review"] is True


def test_extract_retries_once_then_fails(client: TestClient, demo: dict, fake_llm: FakeProvider) -> None:  # type: ignore[type-arg]
    fake_llm.responses += ["esto no es json", _llm_json([{"name": "sopaipillas", "quantity": 3, "unit": "docenas"}])]
    ok = client.post(f"{API}/orders/extract", headers=demo["owner"], json={"text": "3 docenas de sopaipillas"})
    assert ok.status_code == 200
    assert ok.json()["extraction"]["attempts"] == 2
    fake_llm.responses += ['{"items": []}', '{"guests": "muchos"}']
    bad = client.post(f"{API}/orders/extract", headers=demo["owner"], json={"text": "algo raro"})
    assert bad.status_code == 422
    assert bad.json()["code"] == "extraction_failed"
    assert "formulario" in bad.json()["detail"]


def test_extract_without_llm_offers_form(client: TestClient, demo: dict, fake_llm: FakeProvider) -> None:  # type: ignore[type-arg]
    resp = client.post(f"{API}/orders/extract", headers=demo["owner"], json={"text": "3 docenas de sopaipillas"})
    assert resp.status_code == 503
    assert resp.json()["code"] == "llm_unavailable"


# --------------------------------------------------------------------------- cotización


def _order(client: TestClient, headers: dict[str, str], lines: list[dict[str, object]], **extra: object) -> dict:  # type: ignore[type-arg]
    body = {"customer_name": "Cliente de prueba", "event_date": "2026-11-21", "guests": 50, "lines": lines, **extra}
    resp = client.post(f"{API}/orders", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


def _pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)


def test_full_flow_with_missing_price_then_complete(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    h, r = demo["owner"], demo["recipes"]
    order = _order(
        client,
        h,
        [
            {"recipe_id": r["Empanadas de pino"], "requested_name": "empanaditas de pino", "qty": "80"},
            {"recipe_id": r["Canapés de salmón"], "qty": "60"},
        ],
        source="text",
        raw_text="80 empanaditas y 60 canapés",
    )
    started = (datetime.now(UTC) - timedelta(minutes=4)).isoformat()
    q1 = client.post(f"{API}/orders/{order['id']}/quotes", headers=h, json={"started_at": started})
    assert q1.status_code == 201, q1.text
    q1b = q1.json()
    assert q1b["is_complete"] is False
    assert q1b["missing_prices"] == ["Eneldo"]
    pdf = client.get(f"{API}/quotes/{q1b['id']}/pdf", headers=h)
    assert pdf.status_code == 409
    assert "Eneldo" in pdf.json()["detail"]
    assert client.patch(f"{API}/quotes/{q1b['id']}", headers=h, json={"status": "sent"}).status_code == 409

    # se agrega el precio que faltaba y se recalcula: versión 2 completa
    dill = client.get(f"{API}/ingredients?q=eneldo", headers=h).json()["items"][0]
    sup = client.get(f"{API}/suppliers", headers=h).json()[0]
    client.post(
        f"{API}/prices",
        headers=h,
        json={
            "ingredient_id": dill["id"],
            "supplier_id": sup["id"],
            "package_label": "atado 50 g",
            "package_qty": "50",
            "price_clp": 690,
            "price_date": "2026-11-09",
        },
    )
    q2 = client.post(f"{API}/orders/{order['id']}/quotes", headers=h, json={}).json()
    assert q2["version"] == 2
    assert q2["is_complete"] is True
    products = {p["recipe_name"]: p for p in q2["products"]}
    pino = products["Empanadas de pino"]
    assert pino["cost_clp"] == 59738  # igual que GET /recipes/{id}/cost?qty=80 (T04)
    assert pino["unit_price_clp"] == 1045  # 59.738 × 1,4 / 80 = 1.045,4
    assert pino["subtotal_clp"] == 1045 * 80
    assert q2["net_clp"] == sum(p["subtotal_clp"] for p in q2["products"])
    assert q2["total_clp"] == q2["net_clp"] + q2["vat_clp"]

    pdf = client.get(f"{API}/quotes/{q2['id']}/pdf", headers=h)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    text = _pdf_text(pdf.content)
    assert "Cocina Los Aromos (demo)" in text
    assert "Empanadas de pino" in text
    assert "$83.600" in text  # 80 × $1.045
    assert f"${q2['total_clp']:,}".replace(",", ".") in text
    for secret in ("Harina", "Eneldo", "costo", "margen", str(pino["cost_clp"])):
        assert secret not in text  # el PDF no muestra costos internos

    shopping = client.get(f"{API}/quotes/{q2['id']}/shopping-list", headers=h).json()
    assert shopping["total_clp"] == q2["shopping_total_clp"]
    assert all(g["items"] for g in shopping["groups"])

    accepted = client.patch(f"{API}/quotes/{q2['id']}", headers=h, json={"status": "accepted"})
    assert accepted.json()["status"] == "accepted"
    timing = demo["db"].scalars(select(MetricEvent).where(MetricEvent.kind == MetricKind.QUOTE_TIMING)).all()
    assert len(timing) == 1 and 230 <= timing[0].value_num <= 300


def test_old_quote_keeps_its_prices(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    h, r = demo["owner"], demo["recipes"]
    order = _order(client, h, [{"recipe_id": r["Sopaipillas"], "qty": "3", "unit": "dozen"}])
    first = client.post(f"{API}/orders/{order['id']}/quotes", headers=h, json={"use_stock": False}).json()
    flour = client.get(f"{API}/ingredients?q=harina", headers=h).json()["items"][0]
    sup = next(s for s in client.get(f"{API}/suppliers", headers=h).json() if s["name"].startswith("Harinas"))
    client.post(
        f"{API}/prices",
        headers=h,
        json={
            "ingredient_id": flour["id"],
            "supplier_id": sup["id"],
            "package_label": "saco 25 kg",
            "package_qty": "25000",
            "price_clp": 42000,
            "price_date": "2026-11-09",
        },
    )
    second = client.post(f"{API}/orders/{order['id']}/quotes", headers=h, json={"use_stock": False}).json()
    assert second["total_clp"] > first["total_clp"]
    again = client.get(f"{API}/quotes/{first['id']}", headers=h).json()
    assert again["total_clp"] == first["total_clp"]  # la cotización vieja no cambia
    assert again["products"] == first["products"]


def test_quote_validations(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    h, r = demo["owner"], demo["recipes"]
    bad_unit = _order(client, h, [{"recipe_id": r["Mini quiches"], "qty": "2", "unit": "kg"}])
    resp = client.post(f"{API}/orders/{bad_unit['id']}/quotes", headers=h, json={})
    assert resp.status_code == 422
    assert resp.json()["code"] == "quote_calculation"
    lago = login(client, "duena.lago@demo.local", DEFAULT_DEMO_PASSWORD)  # pyme sin margen definido
    lago_order = client.get(f"{API}/orders", headers=lago).json()[0]
    no_margin = client.post(f"{API}/orders/{lago_order['id']}/quotes", headers=lago, json={})
    assert no_margin.json()["code"] == "margin_required"
    with_margin = client.post(f"{API}/orders/{lago_order['id']}/quotes", headers=lago, json={"margin_pct": "35"})
    assert with_margin.status_code == 201
    assert with_margin.json()["margin_pct"] == "35.00"


def test_collaborator_can_take_orders_but_not_quote(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    colab = login(client, "colaboradora.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    order = _order(client, colab, [{"recipe_id": demo["recipes"]["Sopaipillas"], "qty": "12"}])
    assert client.post(f"{API}/orders/{order['id']}/quotes", headers=colab, json={}).status_code == 403


def test_orders_and_quotes_are_isolated(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    h, r = demo["owner"], demo["recipes"]
    order = _order(client, h, [{"recipe_id": r["Sopaipillas"], "qty": "12"}])
    quote = client.post(f"{API}/orders/{order['id']}/quotes", headers=h, json={}).json()
    intruder: Tenant = register(client, "Pyme Intrusa", "intrusa@pyme.cl", PASSWORD)
    assert_isolated(client, intruder, "GET", f"{API}/orders/{order['id']}")
    assert_isolated(client, intruder, "PATCH", f"{API}/orders/{order['id']}", json={"notes": "x"})
    client.patch(f"{API}/pyme", headers=intruder.headers, json={"default_margin_pct": "30"})
    assert_isolated(client, intruder, "POST", f"{API}/orders/{order['id']}/quotes", json={})
    for path in ("", "/pdf", "/shopping-list"):
        assert_isolated(client, intruder, "GET", f"{API}/quotes/{quote['id']}{path}")
    assert_isolated(client, intruder, "PATCH", f"{API}/quotes/{quote['id']}", json={"status": "sent"})
    stolen = client.post(
        f"{API}/orders",
        headers=intruder.headers,
        json={"customer_name": "X Y", "lines": [{"recipe_id": r["Sopaipillas"], "qty": "1"}]},
    )
    assert stolen.status_code == 422
    assert client.get(f"{API}/orders", headers=intruder.headers).json() == []
    assert demo["db"].scalar(select(Order).where(Order.id == order["id"])) is not None


# --------------------------------------------------------------------------- LLM real (opcional)


def _ollama_ready() -> LLMProvider | None:
    if os.environ.get("RUN_LLM_TESTS") != "1":
        return None
    url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
    try:
        httpx.get(f"{url}/api/tags", timeout=2).raise_for_status()
    except httpx.HTTPError:
        return None
    return OllamaProvider(url, os.environ.get("LLM_MODEL", "qwen3:4b"), 120, "10m")


@pytest.mark.llm
def test_real_llm_extraction(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    llm = _ollama_ready()
    if llm is None:
        pytest.skip("RUN_LLM_TESTS=1 y Ollama con el modelo son necesarios")
    client.app.dependency_overrides[get_llm] = lambda: llm  # type: ignore[attr-defined]
    try:
        text = "Necesito 80 empanadas de pino y 3 docenas de sopaipillas para el sábado, somos 40"
        body = client.post(f"{API}/orders/extract", headers=demo["owner"], json={"text": text}).json()
    finally:
        client.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    got = {(line["recipe_name"], line["qty"], line["unit"]) for line in body["lines"]}
    assert ("Empanadas de pino", "80", "unit") in got
    assert ("Sopaipillas", "3", "dozen") in got
    assert body["guests"] == 40

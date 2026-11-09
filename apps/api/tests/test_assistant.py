"""F1 nivel 0 y 1: catálogo, parseo, enrutamiento, consultas con datos reales, caché, verificador y aislamiento."""

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import FakeProvider, get_llm
from app.core.money import format_clp
from app.db.models import AssistantInteraction, Ingredient, Pyme, Recipe
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.assistant import router as assistant_router
from app.modules.assistant import service
from app.modules.assistant.intents import load_catalog
from app.modules.assistant.parsing import parse_qty, parse_range
from app.modules.assistant.verifier import figures_ok
from tests.helpers import login, register

API = "/api/v1"
TODAY = date(2026, 11, 11)  # miércoles


# --------------------------------------------------------------------------- unitarias


def test_catalog_is_valid_and_complete() -> None:
    cat = load_catalog()
    assert len(cat.intents) >= 6
    assert all(len(i.examples) >= 8 for i in cat.intents)
    assert {q.intent for q in cat.quick_actions} <= {i.name for i in cat.intents}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("cuánto me sale la docena de empanadas", 12),
        ("media docena", 6),
        ("dos docenas de canapés", 24),
        ("cuánto cuesta hacer 50 canapés", 50),
        ("para 50 personas", None),  # personas no son unidades
        ("el 22 de noviembre", None),
        ("cuánto cuesta la receta", None),
    ],
)
def test_parse_qty(text: str, expected: int | None) -> None:
    assert parse_qty(text) == (None if expected is None else expected)


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("pedidos de mañana", date(2026, 11, 12), date(2026, 11, 12)),
        ("pedidos de hoy", TODAY, TODAY),
        ("esta semana", TODAY, date(2026, 11, 15)),
        ("la próxima semana", date(2026, 11, 16), date(2026, 11, 22)),
        ("este fin de semana", date(2026, 11, 14), date(2026, 11, 15)),
        ("este mes", TODAY, date(2026, 11, 30)),
        ("el sábado", date(2026, 11, 14), date(2026, 11, 14)),
        ("pedidos", TODAY, date(2026, 11, 18)),  # sin fecha: próximos 7 días
    ],
)
def test_parse_range(text: str, start: date, end: date) -> None:
    assert parse_range(text, TODAY)[:2] == (start, end)


def test_figures_verifier_chilean_formats() -> None:
    facts = "Producir 12 unidades cuesta $21.000 ($1.750 por unidad). Te quedan 2,5 kg."
    assert figures_ok("Te cuesta $21.000, o sea $1.750 cada una.", facts)
    assert figures_ok("Te quedan 2,5 kg.", facts)
    assert not figures_ok("Te cuesta $22.000.", facts)  # cifra inventada
    assert not figures_ok("Son 12 unidades y 3 proveedores.", facts)


# --------------------------------------------------------------------------- integración


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assistant_router, "_today", date.today)  # el seed usa date.today()
    service.CACHE.items.clear()


@pytest.fixture
def demo(client: TestClient, db: Session) -> dict:  # type: ignore[type-arg]
    seed(db)
    pid = db.scalar(select(Pyme.id).where(Pyme.name.like("Cocina%")))  # la sesión de pruebas no filtra por pyme
    return {"owner": login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD), "db": db, "pid": pid}


def ask(client: TestClient, h: dict[str, str], question: str, **extra: object) -> dict:  # type: ignore[type-arg]
    r = client.post(f"{API}/assistant/ask", headers=h, json={"question": question, **extra})
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def test_requires_login(client: TestClient) -> None:
    assert client.post(f"{API}/assistant/ask", json={"question": "hola"}).status_code == 401


def test_stock_level0_with_source(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "¿Cuánta harina me queda?")
    assert out["intent"] == "stock_of_item" and out["level"] == 0 and out["status"] == "ok"
    assert "18 kg" in out["answer"] and "Harina sin polvos" in out["answer"]
    assert out["sources"][0]["label"] == "tu inventario"


def test_ambiguous_item_asks_instead_of_guessing(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "¿Cuánta crema me queda?")
    assert out["status"] == "ambiguous"
    assert {o["label"] for o in out["options"]} >= {"Crema de leche", "Queso crema"}
    assert "kg" not in out["answer"]  # no inventó un dato


def test_unknown_item_says_it_does_not_have_it(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "¿Cuánto caviar me queda?")
    assert out["status"] in ("missing_entity", "ambiguous") and "caviar" not in out["sources"].__str__()


def test_recipe_cost_matches_cost_endpoint(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    recipe = (
        demo["db"]
        .scalars(select(Recipe).where(Recipe.name == "Empanadas de queso", Recipe.pyme_id == demo["pid"]))
        .one()
    )
    cost = client.get(f"{API}/recipes/{recipe.id}/cost", params={"qty": 24}, headers=demo["owner"]).json()
    out = ask(client, demo["owner"], "¿Cuánto me cuestan dos docenas de empanadas de queso?")
    assert out["intent"] == "recipe_cost" and out["status"] == "ok"
    assert format_clp(Decimal(cost["total_clp"])) in out["answer"] and "24" in out["answer"]


def test_upcoming_orders_range(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "¿Qué pedidos tengo en los próximos 30 días?")
    assert out["intent"] == "upcoming_orders"
    assert out["status"] == "ok" and "Cliente demo" in out["answer"]
    assert "cancelado" not in out["answer"]


def test_best_price_and_supplier_info(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    price = ask(client, demo["owner"], "¿Dónde compro más barata la harina?")
    assert price["intent"] == "best_price" and "Cautín" in price["answer"] and "$" in price["answer"]
    sup = ask(client, demo["owner"], "¿Qué días despacha Harinas Cautín?")
    assert sup["intent"] == "supplier_info" and "martes y jueves" in sup["answer"]


def test_unrecognized_question_does_not_invent(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "cuéntame un chiste")
    assert out["status"] == "unrecognized" and out["intent"] is None and out["level"] == 0


def test_quick_actions(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    listed = client.get(f"{API}/assistant/quick-actions", headers=demo["owner"]).json()
    assert {q["id"] for q in listed} >= {"low_stock", "orders_week"}
    out = ask(client, demo["owner"], "x", quick_action="low_stock")
    assert out["intent"] == "low_stock"
    bad = client.post(f"{API}/assistant/ask", headers=demo["owner"], json={"question": "x", "quick_action": "nada"})
    assert bad.status_code == 404


def test_cache_hit_and_invalidation_by_data_version(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    q = "¿Cuánta sal me queda?"
    first, second = ask(client, demo["owner"], q), ask(client, demo["owner"], q)
    assert first["cache_hit"] is False and second["cache_hit"] is True and first["answer"] == second["answer"]
    salt = (
        demo["db"].scalars(select(Ingredient).where(Ingredient.name == "Sal", Ingredient.pyme_id == demo["pid"])).one()
    )
    mv = client.post(
        f"{API}/stock/movements",
        headers=demo["owner"],
        json={"ingredient_id": str(salt.id), "delta_qty": "-1000", "unit": "g", "reason": "adjustment"},
    )
    assert mv.status_code in (200, 201), mv.text
    after = ask(client, demo["owner"], q)
    assert after["cache_hit"] is False and "2 kg" in after["answer"]  # 3 kg - 1 kg, dato nuevo


def test_interaction_is_logged(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    ask(client, demo["owner"], "¿Cuánta harina me queda?")
    row = demo["db"].scalars(select(AssistantInteraction)).one()
    assert (row.intent, row.level, row.cache_hit) == ("stock_of_item", 0, False)
    assert row.queries == ["get_stock"] and row.intents_version == "1" and row.latency_ms >= 0


def test_other_pyme_never_sees_my_data(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    intruder = register(client, "Otra Pyme", "otra@demo.local")
    for q in (
        "¿Cuánta harina me queda?",
        "¿Qué pedidos tengo en los próximos 30 días?",
        "¿Qué días despacha Harinas Cautín?",
    ):
        out = ask(client, intruder.headers, q)
        assert "Harina" not in out["answer"] and "Cliente demo" not in out["answer"] and "Cautín" not in out["answer"]
    mine = ask(client, demo["owner"], "¿Cuánta harina me queda?")
    assert mine["cache_hit"] is False  # la caché es por pyme: la pregunta de la otra no la tocó


# --------------------------------------------------------------------------- nivel 1


@pytest.fixture
def llm(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeProvider]:
    fake = FakeProvider()
    client.app.dependency_overrides[get_llm] = lambda: fake  # type: ignore[attr-defined]
    on = get_settings().model_copy(update={"assistant_use_llm": True})
    monkeypatch.setattr(service, "get_settings", lambda: on)
    yield fake
    client.app.dependency_overrides.clear()  # type: ignore[attr-defined]


Q1 = "¿Cuánto me sale la docena de empanadas de queso?"


def test_level1_uses_llm_when_figures_match(client: TestClient, demo: dict, llm: FakeProvider) -> None:  # type: ignore[type-arg]
    plain = ask(client, demo["owner"], Q1)  # sin respuesta programada: cae a nivel 0 y entrega el dato
    assert plain["level"] == 0 and plain["fallback_reason"] == "llm_unavailable"
    service.CACHE.items.clear()
    llm.responses.append(
        lambda user: json.dumps({"respuesta": "Ojo: " + user.split("<datos>")[1].split("</datos>")[0]})
    )
    out = ask(client, demo["owner"], Q1)
    assert out["level"] == 1 and out["answer"].startswith("Ojo:") and out["fallback_reason"] is None
    assert "<datos>" in llm.calls[-1]  # el dato viajó compacto y delimitado


def test_level1_discards_invented_figure(client: TestClient, demo: dict, llm: FakeProvider) -> None:  # type: ignore[type-arg]
    llm.responses.append(json.dumps({"respuesta": "Te cuesta $999.999 en total."}))
    out = ask(client, demo["owner"], Q1)
    assert out["level"] == 0 and out["fallback_reason"] == "figures_mismatch" and "$999.999" not in out["answer"]


def test_level1_invalid_json_degrades(client: TestClient, demo: dict, llm: FakeProvider) -> None:  # type: ignore[type-arg]
    llm.responses.append("no soy json")
    out = ask(client, demo["owner"], Q1)
    assert out["level"] == 0 and out["fallback_reason"] == "llm_invalid" and out["status"] == "ok"


def test_intent_without_level1_never_calls_llm(client: TestClient, demo: dict, llm: FakeProvider) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "¿Cuánta harina me queda?")
    assert out["level"] == 0 and llm.calls == []


def test_unavailable_llm_result_is_not_cached(client: TestClient, demo: dict, llm: FakeProvider) -> None:  # type: ignore[type-arg]
    assert ask(client, demo["owner"], Q1)["fallback_reason"] == "llm_unavailable"
    llm.responses.append(json.dumps({"respuesta": "Cuesta lo que dice el dato."}))
    again = ask(client, demo["owner"], Q1)
    assert again["cache_hit"] is False and again["level"] == 1  # se reintenta al volver el LLM

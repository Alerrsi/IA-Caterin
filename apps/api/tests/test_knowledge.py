"""Fichas del negocio, sincronización incremental, listas en código y RAG sobre fichas (ADR-006)."""

import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.data_version import bump
from app.core.embeddings import EmbeddingsUnavailableError, FakeEmbeddings, get_embeddings
from app.core.llm import FakeProvider, get_llm
from app.core.tenancy import open_tenant_session
from app.db.enums import DataDomain
from app.db.models import Ingredient, KnowledgeCard, Order, Pyme
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.assistant import router as assistant_router
from app.modules.assistant import service as assistant
from app.modules.knowledge import cards, lists
from app.modules.knowledge import service as knowledge
from tests.helpers import login, register

API = "/api/v1"


class CountingEmbeddings(FakeEmbeddings):
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += len(texts)
        return super().embed(texts)


class DownEmbeddings(FakeEmbeddings):
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingsUnavailableError("sin Ollama")


@pytest.fixture(autouse=True)
def _today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assistant_router, "_today", date.today)
    assistant.CACHE.items.clear()


@pytest.fixture
def demo(client: TestClient, db: Session) -> dict:  # type: ignore[type-arg]
    seed(db)
    pid = db.scalar(select(Pyme.id).where(Pyme.name.like("Cocina%")))
    return {"owner": login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD), "pid": pid}


@pytest.fixture
def tenant_db(demo: dict) -> Iterator[Session]:  # type: ignore[type-arg]
    s = open_tenant_session(demo["pid"])
    yield s
    s.close()


def ask(client: TestClient, h: dict[str, str], question: str) -> dict:  # type: ignore[type-arg]
    r = client.post(f"{API}/assistant/ask", headers=h, json={"question": question})
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


# --------------------------------------------------------------------------- fichas


def test_cards_are_built_from_the_tables(tenant_db: Session) -> None:
    by_title = {c.title: c for c in cards.ingredient_cards(tenant_db)}
    queso = by_title["Queso crema"].text
    assert "Categoría: Lácteos y huevos." in queso and "Stock: 2 kg (mínimo 500 g)." in queso
    assert "Distribuidora Ñielol (demo), pote 1 kg a $7.490" in queso
    pino = next(c for c in cards.recipe_cards(tenant_db) if c.title == "Empanadas de pino").text
    assert "Rinde 12 unidades." in pino and "3 unidades de Huevo" in pino
    supplier = next(c for c in cards.supplier_cards(tenant_db) if c.title.startswith("Verdulería")).text
    assert "Despacha: lunes, miércoles, viernes." in supplier and "Cebolla (malla 1 kg, $990)" in supplier


def test_order_cards_do_not_include_customer_contact(tenant_db: Session) -> None:
    order = tenant_db.scalars(select(Order).where(Order.customer_contact.is_not(None))).first()
    if order is None:  # el seed puede no traer contacto: se agrega uno para la prueba
        order = tenant_db.scalars(select(Order)).first()
        assert order is not None
        order.customer_contact = "+56 9 1234 5678"
        tenant_db.commit()
    texts = " ".join(c.text for c in cards.order_cards(tenant_db))
    assert order.customer_contact not in texts


def test_sync_is_incremental(tenant_db: Session) -> None:
    emb = CountingEmbeddings()
    first = knowledge.sync(tenant_db, emb)
    total = len(list(tenant_db.scalars(select(KnowledgeCard))))
    assert first == total > 30 and knowledge.stale_kinds(tenant_db) == []
    assert knowledge.sync(tenant_db, emb) == 0  # nada cambió: ni regenerar ni vectorizar

    harina = tenant_db.scalars(select(Ingredient).where(Ingredient.name == "Harina sin polvos")).one()
    harina.stock_qty = harina.stock_qty - 1000
    bump(tenant_db, DataDomain.INVENTORY)
    tenant_db.commit()
    assert knowledge.sync(tenant_db, emb) == 1  # solo la ficha de la harina cambió de texto
    card = tenant_db.scalars(select(KnowledgeCard).where(KnowledgeCard.title == "Harina sin polvos")).one()
    assert "Stock: 17 kg" in card.text


def test_inactive_entities_lose_their_card(tenant_db: Session) -> None:
    knowledge.sync(tenant_db, FakeEmbeddings())
    eneldo = tenant_db.scalars(select(Ingredient).where(Ingredient.name == "Eneldo")).one()
    eneldo.is_active = False
    bump(tenant_db, DataDomain.INVENTORY)
    tenant_db.commit()
    knowledge.sync(tenant_db, FakeEmbeddings())
    titles = set(tenant_db.scalars(select(KnowledgeCard.title).where(KnowledgeCard.kind == "ingredient")))
    assert "Eneldo" not in titles and "Huevo" in titles


def test_without_embeddings_cards_exist_and_are_embedded_later(tenant_db: Session) -> None:
    assert knowledge.sync(tenant_db, DownEmbeddings()) == 0
    rows = list(tenant_db.scalars(select(KnowledgeCard)))
    assert rows and all(c.embedding is None for c in rows)
    assert knowledge.search(tenant_db, DownEmbeddings(), "crema de leche", 4, 0.45)  # por texto igual encuentra
    assert knowledge.sync(tenant_db, FakeEmbeddings()) == len(rows)  # al volver Ollama, se vectorizan


def test_other_pyme_never_sees_my_cards(client: TestClient, demo: dict, tenant_db: Session) -> None:  # type: ignore[type-arg]
    knowledge.sync(tenant_db, FakeEmbeddings())
    other = register(client, "Otra Pyme", "otra@demo.local")
    s = open_tenant_session(uuid.UUID(other.pyme_id))
    try:
        assert knowledge.search(s, FakeEmbeddings(), "crema de leche", 8, 0.0) == []
        assert not knowledge.has_cards(s)
    finally:
        s.close()
    out = ask(client, other.headers, "¿qué insumos tengo?")
    assert "Crema de leche" not in out["answer"] and "Harina" not in out["answer"]


# --------------------------------------------------------------------------- listas en código


def test_whole_inventory_is_listed_in_code(client: TestClient, demo: dict, tenant_db: Session) -> None:  # type: ignore[type-arg]
    n = len(list(tenant_db.scalars(select(Ingredient).where(Ingredient.is_active))))
    out = ask(client, demo["owner"], "Que elementos existen actualmente dentro del inventario")
    assert out["level"] == 0 and out["status"] == "ok" and out["answer"].startswith(f"Tienes {n} insumos:")
    assert "Harina sin polvos (18 kg)" in out["answer"] and "Queso crema" in out["answer"]
    assert out["sources"] == [{"kind": "knowledge", "label": "tu inventario"}]


def test_lists_filter_by_category_and_by_terms(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    lacteos = ask(client, demo["owner"], "qué lácteos tengo")["answer"]
    assert lacteos.startswith("Tienes 6 insumos de Lácteos y huevos:") and "Cebolla" not in lacteos
    verduras = ask(client, demo["owner"], "que verduras hay en bodega")["answer"]
    assert "Cebolla" in verduras and "Comino" not in verduras  # categoría, no el texto "Verdulería"
    huevo = ask(client, demo["owner"], "¿qué recetas llevan huevo?")["answer"]
    assert "Empanadas de pino" in huevo and "Empanadas de queso" not in huevo
    assert ask(client, demo["owner"], "¿cuántos proveedores tengo?")["answer"].startswith("Tienes 3 proveedores:")


def test_a_filter_with_no_match_is_never_the_unfiltered_list(tenant_db: Session) -> None:
    knowledge.sync(tenant_db, FakeEmbeddings())
    assert lists.answer(tenant_db, "¿qué recetas llevan chocolate?") is None  # sigue al RAG
    assert lists.answer(tenant_db, "¿cuánta harina me queda?") is None  # no pide una lista


# --------------------------------------------------------------------------- RAG sobre fichas


@pytest.fixture
def text_only(client: TestClient) -> Iterator[None]:
    """Sin embeddings (Ollama caído): la búsqueda queda por texto y la prueba es determinista."""
    client.app.dependency_overrides[get_embeddings] = DownEmbeddings  # type: ignore[attr-defined]
    yield
    client.app.dependency_overrides.pop(get_embeddings, None)  # type: ignore[attr-defined]


def test_open_question_is_answered_from_a_card_without_llm(client: TestClient, demo: dict, text_only: None) -> None:  # type: ignore[type-arg]
    out = ask(client, demo["owner"], "¿quién me vende la crema de leche?")
    assert out["level"] == 2 and "Distribuidora Ñielol" in out["answer"] and "Crema de leche" in out["answer"]
    assert out["answer"].startswith("No estoy seguro")  # sin vectores nunca es confianza alta
    # La ficha del insumo o la del proveedor (las dos dicen quién la vende): siempre una ficha, citada.
    assert out["sources"][0]["kind"] == "knowledge"
    assert out["sources"][0]["label"].startswith(("tu inventario", "tus proveedores"))


def test_open_question_with_llm_gets_the_cards_as_data(
    client: TestClient, demo: dict, monkeypatch: pytest.MonkeyPatch, text_only: None
) -> None:  # type: ignore[type-arg]
    fake = FakeProvider()
    fake.responses.append("La crema de leche te la vende Distribuidora Ñielol (demo).")
    client.app.dependency_overrides[get_llm] = lambda: fake  # type: ignore[attr-defined]
    on = get_settings().model_copy(update={"assistant_use_llm": True})
    monkeypatch.setattr(assistant, "get_settings", lambda: on)
    try:
        out = ask(client, demo["owner"], "¿quién me vende la crema de leche?")
    finally:
        client.app.dependency_overrides.pop(get_llm, None)  # type: ignore[attr-defined]
    assert out["level"] == 2 and out["answer"].startswith("La crema de leche") and out["fallback_reason"] is None
    prompt = fake.calls[-1]
    assert 'fuente="tu' in prompt and "Crema de leche" in prompt  # fichas como datos, delimitadas y citadas
    assert any(s["kind"] == "knowledge" for s in out["sources"])


def test_unexpected_words_do_not_break_lists_but_required_filters_do(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    pescado = ask(client, demo["owner"], "que tipos de pescado hay")["answer"]
    assert pescado.startswith("Tienes 1 insumo de Pescados: Salmón ahumado")  # "tipos" no filtra
    abarrotes = ask(client, demo["owner"], "que abarrotes me quedan")["answer"]
    assert abarrotes.startswith("Tienes ") and "Azúcar" in abarrotes and "Aceite vegetal" in abarrotes
    proveedores = ask(client, demo["owner"], "dime todos los proveedores que tengo anotados")["answer"]
    assert proveedores.startswith("Tienes 3 proveedores:")
    # Lo que va después de "llevan" es obligatorio: sin coincidencias no hay lista (sigue el RAG).
    nueces = ask(client, demo["owner"], "qué recetas llevan nueces")
    assert not nueces["answer"].startswith("Tienes ")
    # "verdulería" no es la categoría "Verduras" (antes la raíz "verdu" las confundía).
    assert not ask(client, demo["owner"], "dame el rut de la verdulería")["answer"].startswith("Tienes ")

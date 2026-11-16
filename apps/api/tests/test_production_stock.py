"""T18: existencias de productos terminados desde la foto. Consumo de insumos, idempotencia, anulación, entregas,
ajustes manuales, aislamiento entre pymes y asistente. Saldos verificados contra el libro con SQL directo."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.enums import BaseUnit, OrderUnit
from app.db.models import Ingredient, Pyme, Recipe, RecipeLine
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.inventory.products import delivery_units
from app.modules.recipes.costing import ConsumptionInput, production_consumption
from tests.helpers import PASSWORD, assert_isolated, login, register

API = "/api/v1"
PINO = "Empanadas de pino"


# --------------------------------------------------------------------------- unitarias


def test_production_consumption_uses_line_then_ingredient_then_pyme_waste() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    lines = [
        ConsumptionInput(a, Decimal(1000), Decimal(10), Decimal(50)),  # merma de la línea: 10 %
        ConsumptionInput(b, Decimal(240), None, Decimal(5)),  # merma del insumo: 5 %
        ConsumptionInput(c, Decimal(12), None, None),  # merma de la pyme: 2 %
    ]
    out = dict(production_consumption(lines, Decimal(24), Decimal(48), Decimal(2)))
    assert out[a] == Decimal("2200.000")  # 1000 × 48/24 × 1,10
    assert out[b] == Decimal("504.000")  # 240 × 2 × 1,05
    assert out[c] == Decimal("24.480")  # 12 × 2 × 1,02
    assert production_consumption(lines, Decimal(24), Decimal(0), Decimal(0)) == []
    with pytest.raises(ValueError):
        production_consumption(lines, Decimal(24), Decimal(-1), Decimal(0))


def test_delivery_units_by_yield_unit() -> None:
    emp, pebre, jugo = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    out = delivery_units(
        [
            (emp, Decimal(3), OrderUnit.DOZEN, BaseUnit.UNIT),
            (emp, Decimal(10), OrderUnit.UNIT, BaseUnit.UNIT),
            (pebre, Decimal("1.5"), OrderUnit.KILOGRAM, BaseUnit.GRAM),
            (jugo, Decimal(2), OrderUnit.LITER, BaseUnit.MILLILITER),
            (emp, Decimal(2), OrderUnit.KILOGRAM, BaseUnit.UNIT),  # no calza: no se descuenta
        ]
    )
    assert out == {emp: Decimal("46.000"), pebre: Decimal("1500.000"), jugo: Decimal("2000.000")}


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def demo(client: TestClient, db: Session) -> dict:  # type: ignore[type-arg]
    seed(db)
    pid = db.scalar(select(Pyme.id).where(Pyme.name.like("Cocina%")))
    recipe = db.scalar(select(Recipe).where(Recipe.pyme_id == pid, Recipe.name == PINO))
    assert recipe is not None and recipe.is_final_product
    return {"owner": login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD), "db": db, "pid": pid, "r": recipe}


def _stocks(db: Session, pid: uuid.UUID, recipe_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    db.expire_all()
    ids = db.scalars(select(RecipeLine.ingredient_id).where(RecipeLine.recipe_id == recipe_id)).all()
    return {i.id: i.stock_qty for i in db.scalars(select(Ingredient).where(Ingredient.id.in_(ids)))}


def _product(db: Session, recipe_id: uuid.UUID) -> Decimal:
    db.expire_all()
    stock = db.scalar(select(Recipe.stock_qty).where(Recipe.id == recipe_id))
    ledger = db.execute(
        text("SELECT coalesce(sum(delta_qty), 0) FROM product_movement WHERE recipe_id = :r"), {"r": recipe_id}
    ).scalar_one()
    assert stock == ledger  # el saldo siempre cuadra con el libro
    assert stock is not None
    return stock


def _produce(client: TestClient, h: dict[str, str], recipe_id: uuid.UUID, qty: int, **extra: object) -> dict:  # type: ignore[type-arg]
    r = client.post(
        f"{API}/vision/productions", headers=h, json={"recipe_id": str(recipe_id), "confirmed_qty": qty, **extra}
    )
    assert r.status_code in (200, 201), r.text
    return r.json()  # type: ignore[no-any-return]


# --------------------------------------------------------------------------- confirmar


def test_confirm_adds_product_and_consumes_recipe_exactly(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    db, pid, r, h = demo["db"], demo["pid"], demo["r"], demo["owner"]
    before = _stocks(db, pid, r.id)
    preview = client.post(
        f"{API}/vision/productions/preview", headers=h, json={"recipe_id": str(r.id), "confirmed_qty": 48}
    )
    assert preview.status_code == 200, preview.text
    out = _produce(client, h, r.id, 48)
    assert out["consumed_ingredients"] is True and Decimal(out["product_stock_qty"]) == 48
    assert _product(db, r.id) == 48
    after = _stocks(db, pid, r.id)
    used = {c["ingredient_id"]: Decimal(c["qty"]) for c in out["consumed"]}
    assert used == {c["ingredient_id"]: Decimal(c["qty"]) for c in preview.json()["consumed"]}  # vista previa = real
    assert len(used) == len(before)
    for iid, qty in before.items():
        assert after[iid] == qty - used[str(iid)]
    # cada descuento quedó en el libro de insumos referenciado a la producción
    n = db.execute(
        text("SELECT count(*) FROM stock_movement WHERE reference_type = 'production' AND reference_id = :p"),
        {"p": out["id"]},
    ).scalar_one()
    assert n == len(used)


def test_retry_with_same_key_does_not_duplicate(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    db, pid, r = demo["db"], demo["pid"], demo["r"]
    h = {**demo["owner"], "Idempotency-Key": str(uuid.uuid4())}
    before = _stocks(db, pid, r.id)
    first = client.post(f"{API}/vision/productions", headers=h, json={"recipe_id": str(r.id), "confirmed_qty": 24})
    again = client.post(f"{API}/vision/productions", headers=h, json={"recipe_id": str(r.id), "confirmed_qty": 24})
    assert first.status_code == 201 and again.status_code == 200 and again.json()["replayed"] is True
    assert [c["qty"] for c in again.json()["consumed"]] == [
        c["qty"] for c in sorted(first.json()["consumed"], key=lambda c: c["name"])
    ]
    assert _product(db, r.id) == 24
    after = _stocks(db, pid, r.id)
    assert sum(before.values()) - sum(after.values()) == sum(Decimal(c["qty"]) for c in first.json()["consumed"])


def test_checkbox_and_pyme_setting_skip_consumption(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    db, pid, r, h = demo["db"], demo["pid"], demo["r"], demo["owner"]
    before = _stocks(db, pid, r.id)
    out = _produce(client, h, r.id, 10, consume_ingredients=False)
    assert out["consumed_ingredients"] is False and out["consumed"] == []
    assert _stocks(db, pid, r.id) == before and _product(db, r.id) == 10

    assert client.patch(f"{API}/pyme", headers=h, json={"production_consumes_ingredients": False}).status_code == 200
    assert client.get(f"{API}/pyme", headers=h).json()["production_consumes_ingredients"] is False
    out = _produce(client, h, r.id, 5)
    assert out["consumed"] == [] and _stocks(db, pid, r.id) == before and _product(db, r.id) == 15
    out = _produce(client, h, r.id, 5, consume_ingredients=True)  # la casilla manda sobre el ajuste
    assert out["consumed"] != []


def test_negative_ingredient_is_flagged_not_blocked(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = _produce(client, demo["owner"], demo["r"].id, 5000)
    assert any(c["went_negative"] for c in out["consumed"])
    assert _product(demo["db"], demo["r"].id) == 5000


def test_zero_count_records_without_moving_stock(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    out = _produce(client, demo["owner"], demo["r"].id, 0)
    assert out["consumed"] == [] and out["consumed_ingredients"] is False
    assert _product(demo["db"], demo["r"].id) == 0


# --------------------------------------------------------------------------- anular e historial


def test_void_restores_everything_once_and_only_owner(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    db, pid, r, h = demo["db"], demo["pid"], demo["r"], demo["owner"]
    before = _stocks(db, pid, r.id)
    out = _produce(client, h, r.id, 36)
    resp = client.post(
        f"{API}/users", headers=h, json={"email": "colab@t18.cl", "full_name": "Colaboradora", "password": PASSWORD}
    )
    assert resp.status_code == 201
    collab = login(client, "colab@t18.cl")
    assert client.post(f"{API}/vision/productions/{out['id']}/void", headers=collab).status_code == 403

    voided = client.post(f"{API}/vision/productions/{out['id']}/void", headers=h)
    assert voided.status_code == 200 and voided.json()["voided_at"] is not None
    assert _stocks(db, pid, r.id) == before and _product(db, r.id) == 0
    again = client.post(f"{API}/vision/productions/{out['id']}/void", headers=h)  # anular dos veces no hace nada
    assert again.status_code == 200 and _product(db, r.id) == 0 and _stocks(db, pid, r.id) == before

    hist = client.get(f"{API}/vision/productions?limit=1", headers=h).json()
    assert hist["items"][0]["id"] == out["id"] and hist["items"][0]["recipe_name"] == PINO
    assert hist["items"][0]["voided_at"] is not None


# --------------------------------------------------------------------------- productos: ajustes y entregas


def test_manual_adjustment_waste_and_movements(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    r, h = demo["r"], demo["owner"]
    _produce(client, h, r.id, 30, consume_ingredients=False)
    key = {**h, "Idempotency-Key": str(uuid.uuid4())}
    body = {"recipe_id": str(r.id), "reason": "waste", "delta_qty": "-6", "note": "Se quemó una bandeja"}
    first = client.post(f"{API}/products/movements", headers=key, json=body)
    again = client.post(f"{API}/products/movements", headers=key, json=body)
    assert first.status_code == 201 and again.status_code == 200 and again.json()["replayed"] is True
    assert Decimal(first.json()["product"]["stock_qty"]) == 24
    bad = client.post(f"{API}/products/movements", headers=h, json={**body, "delta_qty": "6"})
    assert bad.status_code == 422  # una merma no puede sumar
    sys = client.post(f"{API}/products/movements", headers=h, json={**body, "reason": "production"})
    assert sys.status_code == 422  # la producción la registra el sistema
    adj = client.post(f"{API}/products/movements", headers=h, json={**body, "reason": "adjustment", "delta_qty": "-30"})
    assert adj.json()["went_negative"] is True

    stock = {p["name"]: p for p in client.get(f"{API}/products/stock", headers=h).json()}
    assert Decimal(stock[PINO]["stock_qty"]) == -6 and stock[PINO]["recipe_id"] == str(r.id)
    moves = client.get(f"{API}/products/{r.id}/movements?limit=2", headers=h).json()
    assert [m["reason"] for m in moves["items"]] == ["adjustment", "waste"] and moves["next_cursor"]
    rest = client.get(f"{API}/products/{r.id}/movements?limit=2&cursor={moves['next_cursor']}", headers=h).json()
    assert [m["reason"] for m in rest["items"]] == ["production"]
    assert _product(demo["db"], r.id) == -6


def test_delivered_order_discounts_once_and_reverts(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    r, h, db = demo["r"], demo["owner"], demo["db"]
    _produce(client, h, r.id, 60, consume_ingredients=False)
    body = {
        "customer_name": "Cliente T18",
        "event_date": "2026-11-20",
        "lines": [{"recipe_id": str(r.id), "qty": "3", "unit": "dozen"}],
    }
    order = client.post(f"{API}/orders", headers=h, json=body).json()
    patch = lambda data: client.patch(f"{API}/orders/{order['id']}", headers=h, json=data)  # noqa: E731
    assert patch({"status": "confirmed"}).status_code == 200 and _product(db, r.id) == 60
    assert patch({"status": "delivered"}).status_code == 200 and _product(db, r.id) == 24
    assert patch({"status": "delivered", "notes": "otra vez"}).status_code == 200 and _product(db, r.id) == 24
    lines = [{"recipe_id": str(r.id), "qty": "4", "unit": "dozen"}]
    assert patch({"lines": lines}).status_code == 200 and _product(db, r.id) == 12  # corrigió el pedido: 48
    assert patch({"status": "confirmed"}).status_code == 200 and _product(db, r.id) == 60  # vuelve atrás
    reasons = [m["reason"] for m in client.get(f"{API}/products/{r.id}/movements", headers=h).json()["items"]]
    assert reasons.count("delivery") == 2 and reasons.count("void") == 1


# --------------------------------------------------------------------------- aislamiento y asistente


def test_products_and_productions_are_isolated(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    r, h = demo["r"], demo["owner"]
    out = _produce(client, h, r.id, 12)
    other = register(client, "Pyme Vecina", "vecina@t18.cl")
    assert_isolated(client, other, "GET", f"{API}/products/{r.id}/movements")
    assert_isolated(client, other, "POST", f"{API}/vision/productions/{out['id']}/void")
    assert_isolated(
        client, other, "POST", f"{API}/vision/productions/preview", {"recipe_id": str(r.id), "confirmed_qty": 1}
    )
    assert_isolated(
        client,
        other,
        "POST",
        f"{API}/products/movements",
        {"recipe_id": str(r.id), "reason": "adjustment", "delta_qty": "1"},
    )
    assert client.get(f"{API}/products/stock", headers=other.headers).json() == []
    assert client.get(f"{API}/vision/productions", headers=other.headers).json()["items"] == []
    assert _product(demo["db"], r.id) == 12


def test_assistant_answers_ready_products_without_llm(client: TestClient, demo: dict) -> None:  # type: ignore[type-arg]
    r, h = demo["r"], demo["owner"]
    ask = lambda q: client.post(f"{API}/assistant/ask", headers=h, json={"question": q}).json()  # noqa: E731
    none = ask("¿Qué productos tengo listos para entregar?")
    assert none["intent"] == "product_stock" and none["level"] == 0 and "No tienes productos listos" in none["answer"]
    _produce(client, h, r.id, 48, consume_ingredients=False)
    one = ask("¿Cuántas empanadas de pino tengo listas?")
    assert one["intent"] == "product_stock" and one["level"] == 0
    assert "48 unidades de Empanadas de pino" in one["answer"]

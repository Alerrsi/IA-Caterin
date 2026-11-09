import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Recipe
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from tests.helpers import Tenant, assert_isolated, login, register
from tests.test_inventory import new_ingredient

API = "/api/v1"


@pytest.fixture
def a(client: TestClient) -> Tenant:
    return register(client, "Pyme A", "a@pyme.cl")


def new_supplier(client: TestClient, t: Tenant, name: str = "Molino", **extra: object) -> dict[str, object]:
    resp = client.post(f"{API}/suppliers", headers=t.headers, json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


def new_price(client: TestClient, t: Tenant, ing: str, sup: str, **extra: object) -> dict[str, object]:
    body = {
        "ingredient_id": ing,
        "supplier_id": sup,
        "package_label": "saco 25 kg",
        "package_qty": "25",
        "package_unit": "kg",
        "price_clp": 21000,
        "price_date": "2026-11-02",
        **extra,
    }
    resp = client.post(f"{API}/prices", headers=t.headers, json=body)
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


def test_supplier_crud_and_validation(client: TestClient, a: Tenant) -> None:
    sup = new_supplier(client, a, "Molino Sur", delivery_days=[4, 2, 2])
    assert sup["delivery_days"] == [2, 4]
    bad = client.post(f"{API}/suppliers", headers=a.headers, json={"name": "X Y", "delivery_days": [8]})
    assert bad.status_code == 422
    assert client.post(f"{API}/suppliers", headers=a.headers, json={"name": "molino sur"}).status_code == 409
    upd = client.patch(f"{API}/suppliers/{sup['id']}", headers=a.headers, json={"phone": "+56 9 1111 1111"})
    assert upd.json()["phone"] == "+56 9 1111 1111"


def test_prices_are_versioned_and_compared(client: TestClient, a: Tenant) -> None:
    flour = new_ingredient(client, a, "Harina")
    molino, dist = new_supplier(client, a, "Molino"), new_supplier(client, a, "Distribuidora")
    old = new_price(client, a, flour["id"], molino["id"])
    assert old["package_qty"] == "25000.000"
    new = new_price(client, a, flour["id"], molino["id"], price_clp=19500)
    net = new_price(
        client,
        a,
        flour["id"],
        dist["id"],
        package_label="bolsa 1 kg",
        package_qty="1",
        price_clp=700,
        includes_vat=False,
    )
    current = client.get(f"{API}/prices?ingredient_id={flour['id']}", headers=a.headers).json()
    assert {p["id"] for p in current} == {new["id"], net["id"]}
    history = client.get(f"{API}/prices?ingredient_id={flour['id']}&include_history=true", headers=a.headers).json()
    assert old["id"] in {p["id"] for p in history}

    cmp = client.get(f"{API}/ingredients/{flour['id']}/prices", headers=a.headers).json()
    items = cmp["items"]
    assert [i["supplier_name"] for i in items] == ["Molino", "Distribuidora"]
    assert items[0]["price_per_reference_clp"] == 780  # 19.500 / 25
    assert items[0]["reference_unit"] == "kg"
    assert items[0]["is_best"] is True
    assert items[1]["gross_price_clp"] == 833  # 700 neto + 19 %
    assert items[1]["price_per_reference_clp"] == 833
    assert items[1]["is_best"] is False


def test_recipe_crud_cost_and_versions(client: TestClient, a: Tenant) -> None:
    flour = new_ingredient(client, a, "Harina")
    dill = new_ingredient(client, a, "Eneldo")
    sup = new_supplier(client, a)
    new_price(client, a, flour["id"], sup["id"])
    body = {
        "name": "Masa",
        "yield_qty": "12",
        "lines": [
            {"ingredient_id": flour["id"], "qty": "0.6", "unit": "kg"},
            {"ingredient_id": dill["id"], "qty": "5"},
        ],
    }
    resp = client.post(f"{API}/recipes", headers=a.headers, json=body)
    assert resp.status_code == 201, resp.text
    recipe = resp.json()
    assert recipe["lines"][0]["qty"] == "600.000"
    assert recipe["lines"][0]["ingredient_name"] == "Harina"
    cost = client.get(f"{API}/recipes/{recipe['id']}/cost", headers=a.headers).json()
    assert cost["total_clp"] == 504  # 600 g × 0,84, sin merma (la pyme nueva tiene 0 %)
    assert cost["is_complete"] is False
    assert cost["missing_prices"] == ["Eneldo"]
    cost80 = client.get(f"{API}/recipes/{recipe['id']}/cost?qty=24", headers=a.headers).json()
    assert cost80["total_clp"] == 1008

    dup = {**body, "lines": [body["lines"][0], body["lines"][0]]}
    assert client.post(f"{API}/recipes", headers=a.headers, json={**dup, "name": "Otra"}).status_code == 422
    upd = client.patch(f"{API}/recipes/{recipe['id']}", headers=a.headers, json={"lines": [body["lines"][0]]})
    assert upd.json()["version"] == 2
    assert len(upd.json()["lines"]) == 1
    same = client.patch(f"{API}/recipes/{recipe['id']}", headers=a.headers, json={"notes": "Reposar 30 min"})
    assert same.json()["version"] == 2


def test_seed_recipe_cost_matches_hand_calculation(client: TestClient, db: Session) -> None:
    """Ver tests/fixtures/costo_empanadas_pino.md."""
    seed(db)
    headers = login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    recipe = db.scalar(select(Recipe).where(Recipe.name == "Empanadas de pino"))
    assert recipe is not None
    cost = client.get(f"{API}/recipes/{recipe.id}/cost", headers=headers).json()
    by_name = {line["ingredient_name"]: line["cost_clp"] for line in cost["lines"]}
    assert by_name == {
        "Harina sin polvos": 529,
        "Manteca": 377,
        "Carne molida": 5873,
        "Cebolla": 762,
        "Huevo": 681,
        "Aceituna negra": 440,
        "Pasas": 209,
        "Comino": 31,
        "Ají de color": 52,
        "Sal": 6,
    }
    assert cost["total_clp"] == 8960
    assert cost["per_unit_clp"] == 747
    assert cost["is_complete"] is True


def test_suppliers_and_recipes_are_isolated(client: TestClient, a: Tenant) -> None:
    b = register(client, "Pyme B", "b@pyme.cl")
    flour_a = new_ingredient(client, a, "Harina")
    sup_a = new_supplier(client, a)
    price_body = {
        "ingredient_id": flour_a["id"],
        "supplier_id": sup_a["id"],
        "package_label": "1 kg",
        "package_qty": "1000",
        "price_clp": 1000,
        "price_date": "2026-11-02",
    }
    recipe = client.post(
        f"{API}/recipes",
        headers=a.headers,
        json={"name": "Masa", "yield_qty": "1", "lines": [{"ingredient_id": flour_a["id"], "qty": "1"}]},
    ).json()
    assert_isolated(client, b, "GET", f"{API}/suppliers/{sup_a['id']}")
    assert_isolated(client, b, "PATCH", f"{API}/suppliers/{sup_a['id']}", json={"notes": "x"})
    assert_isolated(client, b, "POST", f"{API}/prices", json=price_body)
    assert_isolated(client, b, "GET", f"{API}/ingredients/{flour_a['id']}/prices")
    assert_isolated(client, b, "GET", f"{API}/recipes/{recipe['id']}")
    assert_isolated(client, b, "GET", f"{API}/recipes/{recipe['id']}/cost")
    assert_isolated(client, b, "PATCH", f"{API}/recipes/{recipe['id']}", json={"notes": "x"})
    # B no puede armar una receta con un insumo de A
    stolen = client.post(
        f"{API}/recipes",
        headers=b.headers,
        json={"name": "Masa", "yield_qty": "1", "lines": [{"ingredient_id": flour_a["id"], "qty": "1"}]},
    )
    assert stolen.status_code == 422
    assert stolen.json()["code"] == "ingredient_not_found"
    assert client.get(f"{API}/suppliers", headers=b.headers).json() == []
    assert client.get(f"{API}/recipes", headers=b.headers).json() == []
    assert client.get(f"{API}/prices", headers=b.headers).json() == []

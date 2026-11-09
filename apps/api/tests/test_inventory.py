import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.enums import DataDomain
from app.db.models import DataVersion
from app.db.session import get_sessionmaker
from tests.helpers import Tenant, assert_isolated, register

API = "/api/v1"


@pytest.fixture
def a(client: TestClient) -> Tenant:
    return register(client, "Pyme A", "a@pyme.cl")


def new_ingredient(client: TestClient, t: Tenant, name: str, unit: str = "g", **extra: object) -> dict[str, object]:
    resp = client.post(f"{API}/ingredients", headers=t.headers, json={"name": name, "base_unit": unit, **extra})
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


def version(pyme_id: str, domain: DataDomain) -> int:
    with get_sessionmaker()() as s:
        return int(
            s.scalar(
                select(DataVersion.version).where(
                    DataVersion.pyme_id == uuid.UUID(pyme_id), DataVersion.domain == domain
                )
            )
            or 0
        )


def test_create_with_initial_stock_records_movement(client: TestClient, a: Tenant) -> None:
    before = version(a.pyme_id, DataDomain.INVENTORY)
    ing = new_ingredient(client, a, "  Harina   sin polvos ", initial_stock="18000", min_stock_qty="20000")
    assert ing["name"] == "Harina sin polvos"
    assert ing["stock_qty"] == "18000.000"
    assert ing["is_low"] is True
    movements = client.get(f"{API}/ingredients/{ing['id']}/movements", headers=a.headers).json()["items"]
    assert [m["delta_qty"] for m in movements] == ["18000.000"]
    assert version(a.pyme_id, DataDomain.INVENTORY) > before
    dup = client.post(f"{API}/ingredients", headers=a.headers, json={"name": "HARINA SIN POLVOS", "base_unit": "g"})
    assert dup.status_code == 409


def test_list_pagination_search_and_etag(client: TestClient, a: Tenant) -> None:
    for name in ("Azúcar", "Cebolla", "Huevo", "Leche", "Sal"):
        new_ingredient(client, a, name)
    first = client.get(f"{API}/ingredients?limit=2", headers=a.headers)
    body = first.json()
    assert [i["name"] for i in body["items"]] == ["Azúcar", "Cebolla"]
    second = client.get(f"{API}/ingredients?limit=2&cursor={body['next_cursor']}", headers=a.headers).json()
    assert [i["name"] for i in second["items"]] == ["Huevo", "Leche"]
    third = client.get(f"{API}/ingredients?limit=2&cursor={second['next_cursor']}", headers=a.headers).json()
    assert [i["name"] for i in third["items"]] == ["Sal"]
    assert third["next_cursor"] is None
    assert [i["name"] for i in client.get(f"{API}/ingredients?q=ech", headers=a.headers).json()["items"]] == ["Leche"]
    etag = first.headers["etag"]
    cached = client.get(f"{API}/ingredients?limit=2", headers={**a.headers, "If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""
    assert client.get(f"{API}/ingredients?cursor=%%%", headers=a.headers).status_code == 400


def test_movements_units_signs_and_idempotency(client: TestClient, a: Tenant) -> None:
    ing = new_ingredient(client, a, "Harina")
    move = {"ingredient_id": ing["id"], "reason": "purchase", "delta_qty": "2.5", "unit": "kg"}
    key = {"Idempotency-Key": str(uuid.uuid4())}
    first = client.post(f"{API}/stock/movements", headers={**a.headers, **key}, json=move)
    assert first.status_code == 201
    assert first.json()["ingredient"]["stock_qty"] == "2500.000"
    again = client.post(f"{API}/stock/movements", headers={**a.headers, **key}, json=move)
    assert again.status_code == 200
    assert again.json()["replayed"] is True
    assert again.json()["ingredient"]["stock_qty"] == "2500.000"  # no se duplicó

    bad_sign = {**move, "reason": "consumption"}
    assert client.post(f"{API}/stock/movements", headers=a.headers, json=bad_sign).status_code == 422
    bad_unit = {**move, "unit": "litros"}
    assert client.post(f"{API}/stock/movements", headers=a.headers, json=bad_unit).json()["code"] == "unit_conversion"
    out = {"ingredient_id": ing["id"], "reason": "consumption", "delta_qty": "-3000"}
    resp = client.post(f"{API}/stock/movements", headers=a.headers, json=out)
    assert resp.json()["went_negative"] is True
    assert resp.json()["ingredient"]["stock_qty"] == "-500.000"
    bad_key = client.post(f"{API}/stock/movements", headers={**a.headers, "Idempotency-Key": "no"}, json=move)
    assert bad_key.status_code == 400


def test_low_stock_and_deactivate(client: TestClient, a: Tenant) -> None:
    low = new_ingredient(client, a, "Crema", "ml", initial_stock="500", min_stock_qty="1000")
    new_ingredient(client, a, "Sal", initial_stock="3000", min_stock_qty="100")
    assert [i["name"] for i in client.get(f"{API}/stock/low", headers=a.headers).json()] == ["Crema"]
    assert client.delete(f"{API}/ingredients/{low['id']}", headers=a.headers).status_code == 204
    names = [i["name"] for i in client.get(f"{API}/ingredients", headers=a.headers).json()["items"]]
    assert names == ["Sal"]
    move = {"ingredient_id": low["id"], "reason": "purchase", "delta_qty": "1"}
    assert client.post(f"{API}/stock/movements", headers=a.headers, json=move).status_code == 409


def test_inventory_is_isolated(client: TestClient, a: Tenant) -> None:
    b = register(client, "Pyme B", "b@pyme.cl")
    ing = new_ingredient(client, a, "Harina", initial_stock="100")
    path = f"{API}/ingredients/{ing['id']}"
    assert_isolated(client, b, "GET", path)
    assert_isolated(client, b, "PATCH", path, json={"name": "Robada"})
    assert_isolated(client, b, "DELETE", path)
    assert_isolated(client, b, "GET", f"{path}/movements")
    assert_isolated(
        client,
        b,
        "POST",
        f"{API}/stock/movements",
        json={"ingredient_id": ing["id"], "reason": "purchase", "delta_qty": "1"},
    )
    assert client.get(f"{API}/ingredients", headers=b.headers).json()["items"] == []
    assert client.get(path, headers=a.headers).json()["stock_qty"] == "100.000"

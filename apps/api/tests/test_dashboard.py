"""T17: tablero del negocio. Agregación pura, endpoint, permisos, aislamiento A/B y venta contra SQL directo."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.enums import OrderUnit
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.dashboard import service
from app.modules.dashboard.service import ProductLine, SoldOrder
from tests.helpers import PASSWORD, login, register

API = "/api/v1"


# --------------------------------------------------------------------------- unitarias


def test_window_covers_whole_months_and_crosses_years() -> None:
    assert service.window(date(2026, 11, 16), 6) == (date(2026, 6, 1), date(2026, 11, 30))
    assert service.window(date(2026, 2, 10), 3) == (date(2025, 12, 1), date(2026, 2, 28))
    assert service.window(date(2026, 1, 31), 1) == (date(2026, 1, 1), date(2026, 1, 31))
    assert service.month_keys(date(2025, 12, 1), 3) == ["2025-12", "2026-01", "2026-02"]


def test_sales_by_month_keeps_empty_months_and_skips_orders_without_quote() -> None:
    orders = [
        SoldOrder(date(2026, 9, 3), Decimal(100000), Decimal(60000), Decimal(119000)),
        SoldOrder(date(2026, 9, 20), Decimal(50000), Decimal(40000), Decimal(59500)),
        SoldOrder(date(2026, 11, 1), None, None, None),  # confirmado sin cotización aceptada
        SoldOrder(date(2026, 5, 1), Decimal(1), Decimal(1), Decimal(1)),  # fuera del periodo
    ]
    rows = service.sales_by_month(orders, ["2026-09", "2026-10", "2026-11"])
    assert [r.month for r in rows] == ["2026-09", "2026-10", "2026-11"]
    sep, octo, nov = rows
    assert (sep.orders, sep.net_clp, sep.ingredients_cost_clp, sep.margin_clp, sep.total_clp) == (
        2,
        150000,
        100000,
        50000,
        178500,
    )
    assert octo.orders == 0 and octo.total_clp == 0
    assert nov.orders == 0  # el pedido sin cotización no suma dinero


def test_sales_kpis_margin_ticket_and_no_sales() -> None:
    orders = [
        SoldOrder(date(2026, 9, 3), Decimal(100000), Decimal(60000), Decimal(119000)),
        SoldOrder(date(2026, 9, 4), Decimal(50000), Decimal(40000), Decimal(59501)),
        SoldOrder(date(2026, 9, 5), None, None, None),
    ]
    k = service.sales_kpis(orders)
    assert k["sales_total_clp"] == 178501
    assert k["margin_clp"] == 50000
    assert k["margin_pct"] == 33.3  # 50.000 / 150.000
    assert k["sold_orders"] == 2
    assert k["avg_ticket_clp"] == 89251  # 89.250,5 -> mitad hacia arriba
    assert k["orders_without_quote"] == 1
    empty = service.sales_kpis([])
    assert empty["margin_pct"] is None and empty["avg_ticket_clp"] is None and empty["sales_total_clp"] == 0


def test_top_products_counts_dozens_and_excludes_weights() -> None:
    pino, queso, pebre = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    lines = [
        ProductLine(o1, pino, "Empanadas de pino", Decimal(2), OrderUnit.DOZEN),
        ProductLine(o2, pino, "Empanadas de pino", Decimal(10), OrderUnit.UNIT),
        ProductLine(o1, queso, "Empanadas de queso", Decimal(30), OrderUnit.PORTION),
        ProductLine(o2, pebre, "Pebre", Decimal(3), OrderUnit.KILOGRAM),
    ]
    top = service.top_products(lines)
    assert [(p.name, p.units, p.orders) for p in top.items] == [
        ("Empanadas de pino", "34", 2),
        ("Empanadas de queso", "30", 1),
    ]
    assert top.excluded_lines == 1
    assert len(service.top_products(lines, limit=1).items) == 1


def test_supplier_spend_groups_the_rest_in_others() -> None:
    rows = [(uuid.uuid4(), f"Proveedor {i}", Decimal(1000 * (i + 1))) for i in range(7)]
    rows.append((uuid.uuid4(), "Sin compras", Decimal(0)))
    out = service.supplier_spend(rows, limit=5)
    assert [s.name for s in out] == [f"Proveedor {i}" for i in (6, 5, 4, 3, 2)] + ["Otros"]
    assert out[-1].supplier_id is None and out[-1].amount_clp == 3000  # 1.000 + 2.000
    assert service.supplier_spend(rows[:2]) == service.supplier_spend(rows[:2], limit=5)  # sin «Otros» si no sobra


def test_pct_of_min() -> None:
    assert service.pct_of_min(Decimal(250), Decimal(1000)) == 25.0
    assert service.pct_of_min(Decimal(-5), Decimal(1000)) == 0.0
    assert service.pct_of_min(Decimal(5), Decimal(0)) == 100.0


# --------------------------------------------------------------------------- endpoint


@pytest.fixture
def demo(client: TestClient, db: Session) -> dict[str, str]:
    seed(db)
    owner = login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    recipes = client.get(f"{API}/recipes?q=empanadas de pino", headers=owner).json()
    items = recipes["items"] if isinstance(recipes, dict) else recipes
    return {"recipe_id": items[0]["id"], **owner}


def _headers(demo: dict[str, str]) -> dict[str, str]:
    return {"Authorization": demo["Authorization"]}


def _sold_order(client: TestClient, h: dict[str, str], recipe_id: str, event: date) -> dict:  # type: ignore[type-arg]
    body = {
        "customer_name": "Cliente del tablero",
        "event_date": event.isoformat(),
        "guests": 40,
        "lines": [{"recipe_id": recipe_id, "qty": "3", "unit": "dozen"}],
    }
    order = client.post(f"{API}/orders", headers=h, json=body)
    assert order.status_code == 201, order.text
    quote = client.post(f"{API}/orders/{order.json()['id']}/quotes", headers=h, json={})
    assert quote.status_code == 201, quote.text
    q = quote.json()
    assert q["is_complete"], q
    assert client.patch(f"{API}/quotes/{q['id']}", headers=h, json={"status": "accepted"}).status_code == 200
    oid = order.json()["id"]
    assert client.patch(f"{API}/orders/{oid}", headers=h, json={"status": "confirmed"}).status_code == 200
    return dict(q)


def test_dashboard_reflects_a_new_sale(client: TestClient, demo: dict[str, str]) -> None:
    h = _headers(demo)
    before = client.get(f"{API}/dashboard", headers=h)
    assert before.status_code == 200, before.text
    b = before.json()
    assert b["period"]["months"] == 6 and len(b["sales_by_month"]) == 6
    assert len(b["upcoming_by_day"]) == 14
    assert [s["status"] for s in b["orders_by_status"]] == ["requested", "draft", "confirmed", "delivered", "cancelled"]

    today = date.fromisoformat(b["period"]["today"])
    q = _sold_order(client, h, demo["recipe_id"], today + timedelta(days=2))
    a = client.get(f"{API}/dashboard", headers=h).json()
    ka, kb = a["kpis"], b["kpis"]
    assert ka["sold_orders"] == kb["sold_orders"] + 1
    assert ka["sales_total_clp"] == kb["sales_total_clp"] + q["total_clp"]
    assert ka["upcoming_7d"] == kb["upcoming_7d"] + 1
    month = (today + timedelta(days=2)).strftime("%Y-%m")
    if month == a["sales_by_month"][-1]["month"]:  # el evento cae en el mes en curso
        assert a["sales_by_month"][-1]["total_clp"] == b["sales_by_month"][-1]["total_clp"] + q["total_clp"]
    pino = next(p for p in a["top_products"]["items"] if p["recipe_id"] == demo["recipe_id"])
    assert Decimal(pino["units"]) >= 36  # 3 docenas
    assert sum(d["confirmed"] for d in a["upcoming_by_day"]) >= 1


def test_month_sales_match_direct_sql(client: TestClient, demo: dict[str, str], db: Session) -> None:
    h = _headers(demo)
    today = date.fromisoformat(client.get(f"{API}/dashboard", headers=h).json()["period"]["today"])
    _sold_order(client, h, demo["recipe_id"], today)
    _sold_order(client, h, demo["recipe_id"], today)
    body = client.get(f"{API}/dashboard?months=1", headers=h).json()
    sql = text(
        """
        SELECT coalesce(sum(q.total_clp), 0), count(*)
        FROM catering_order o
        JOIN LATERAL (
            SELECT total_clp FROM quote
            WHERE order_id = o.id AND pyme_id = o.pyme_id AND status = 'accepted'
            ORDER BY version DESC LIMIT 1
        ) q ON true
        JOIN pyme p ON p.id = o.pyme_id AND p.name = 'Cocina Los Aromos (demo)'
        WHERE o.status IN ('confirmed', 'delivered')
          AND coalesce(o.event_date, (o.created_at AT TIME ZONE 'America/Santiago')::date)
              BETWEEN :d_from AND :d_to
        """
    )
    period = body["period"]
    total, n = db.execute(sql, {"d_from": period["date_from"], "d_to": period["date_to"]}).one()
    assert n >= 2
    assert body["sales_by_month"][0]["total_clp"] == int(total)
    assert body["kpis"]["sold_orders"] == n


def test_only_the_owner_sees_the_dashboard(client: TestClient, demo: dict[str, str]) -> None:
    h = _headers(demo)
    resp = client.post(
        f"{API}/users", headers=h, json={"email": "colab@tablero.cl", "full_name": "Colaboradora", "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    collab = login(client, "colab@tablero.cl")
    denied = client.get(f"{API}/dashboard", headers=collab)
    assert denied.status_code == 403
    assert denied.json()["code"] == "owner_only"
    assert client.get(f"{API}/dashboard").status_code == 401
    assert client.get(f"{API}/dashboard?months=13", headers=h).status_code == 422
    assert client.get(f"{API}/dashboard?months=0", headers=h).status_code == 422


def test_dashboard_is_isolated_between_pymes(client: TestClient, demo: dict[str, str]) -> None:
    h = _headers(demo)
    today = date.fromisoformat(client.get(f"{API}/dashboard", headers=h).json()["period"]["today"])
    _sold_order(client, h, demo["recipe_id"], today + timedelta(days=1))
    other = register(client, "Pyme Vecina", "vecina@tablero.cl")
    body = client.get(f"{API}/dashboard?months=12", headers=other.headers).json()
    k = body["kpis"]
    assert (k["sales_total_clp"], k["sold_orders"], k["upcoming_7d"], k["low_stock"], k["pending_requests"]) == (
        0,
        0,
        0,
        0,
        0,
    )
    assert all(m["total_clp"] == 0 for m in body["sales_by_month"])
    assert body["top_products"]["items"] == [] and body["spend_by_supplier"] == []
    assert body["low_stock"]["items"] == []
    assert all(s["orders"] == 0 for s in body["orders_by_status"])

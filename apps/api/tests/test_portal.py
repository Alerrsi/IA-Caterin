"""Portal de clientes (ADR-007): registro por enlace, cotizar, guardar, enviar y la decisión de la dueña.

Lo más importante: un cliente no entra a ninguna ruta de la pyme y no ve costos, margen ni insumos.
"""

import io
import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.llm import FakeProvider, get_llm
from app.db.models import Order, Pyme, Recipe
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed
from app.modules.portal import service
from tests.helpers import PASSWORD, login

API = "/api/v1"
# Lo que el cliente nunca debe ver en las respuestas del portal (vienen de los insumos y la configuración).
INTERNAL = ("cost", "margin", "ingredient", "supplier", "Harina sin polvos", "Distribuidora", "stock")


def _register(client: TestClient, code: str, email: str, name: str = "Cliente Prueba") -> dict[str, Any]:
    resp = client.post(
        f"{API}/portal/register", json={"code": code, "full_name": name, "email": email, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def portal(client: TestClient, db: Session) -> dict[str, Any]:
    seed(db)
    owner = login(client, "duena.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    lago = login(client, "duena.lago@demo.local", DEFAULT_DEMO_PASSWORD)
    code = client.post(f"{API}/pyme/customer-code", headers=owner).json()["customer_code"]
    a = _register(client, code, "cliente.a@prueba.local", "Ana Cliente")
    b = _register(client, code, "cliente.b@prueba.local", "Beto Cliente")
    recipes = {name: str(rid) for name, rid in db.execute(select(Recipe.name, Recipe.id)).all()}
    return {
        "owner": owner,
        "lago": lago,
        "code": code,
        "a": {"Authorization": f"Bearer {a['access_token']}"},
        "b": {"Authorization": f"Bearer {b['access_token']}"},
        "token_a": a,
        "recipes": recipes,
        "db": db,
    }


@pytest.fixture
def fake_llm(client: TestClient) -> Iterator[FakeProvider]:
    fake = FakeProvider()
    client.app.dependency_overrides[get_llm] = lambda: fake  # type: ignore[attr-defined]
    yield fake
    client.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def _request(client: TestClient, headers: dict[str, str], recipe_id: str, qty: str = "2", unit: str = "dozen") -> Any:
    body = {
        "event_date": "2026-12-12",
        "guests": 30,
        "notes": "sin cebolla",
        "lines": [{"recipe_id": recipe_id, "qty": qty, "unit": unit}],
    }
    resp = client.post(f"{API}/portal/requests", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- acceso


def test_customer_cannot_use_any_staff_route(client: TestClient, portal: dict[str, Any]) -> None:
    """Recorre TODAS las rutas del OpenAPI: fuera de /auth, /portal y /health, un cliente recibe 403."""
    some_id = str(uuid.uuid4())
    checked = 0
    for path, ops in client.get(f"{API}/openapi.json").json()["paths"].items():
        local = path.removeprefix(API)
        # /imports/templates: planillas de ejemplo públicas, sin datos de ninguna pyme.
        if local.startswith(("/auth/", "/portal", "/health", "/imports/templates/")):
            continue
        url = re.sub(r"\{[^}]+\}", some_id, path)
        for method in ops:
            resp = client.request(method.upper(), url, headers=portal["a"], json={})
            assert resp.status_code == 403, f"{method} {local} -> {resp.status_code}"
            assert resp.json()["code"] in ("staff_only", "owner_only"), f"{method} {local}"
            checked += 1
    assert checked > 40


def test_staff_cannot_use_customer_routes(client: TestClient, portal: dict[str, Any]) -> None:
    resp = client.get(f"{API}/portal/requests", headers=portal["owner"])
    assert resp.status_code == 403 and resp.json()["code"] == "customer_only"


def test_customer_session_hides_pyme_settings(client: TestClient, portal: dict[str, Any]) -> None:
    pyme = portal["token_a"]["pyme"]
    assert pyme["name"] == "Cocina Los Aromos (demo)"
    assert "default_margin_pct" not in pyme and "customer_code" not in pyme
    assert portal["token_a"]["user"]["role"] == "customer"
    me = client.get(f"{API}/auth/me", headers=portal["a"]).json()
    assert me["user"]["email"] == "cliente.a@prueba.local" and "default_margin_pct" not in me["pyme"]


def test_register_needs_a_valid_open_code(client: TestClient, portal: dict[str, Any]) -> None:
    bad = client.post(
        f"{API}/portal/register",
        json={"code": "no-existe-123", "full_name": "X Y", "email": "x@prueba.local", "password": PASSWORD},
    )
    assert bad.status_code == 404 and bad.json()["code"] == "portal_code_not_found"
    assert client.get(f"{API}/portal/pymes/{portal['code']}").json()["name"] == "Cocina Los Aromos (demo)"
    taken = client.post(
        f"{API}/portal/register",
        json={"code": portal["code"], "full_name": "Otra", "email": "duena.aromos@demo.local", "password": PASSWORD},
    )
    assert taken.status_code == 409
    client.delete(f"{API}/pyme/customer-code", headers=portal["owner"])
    closed = client.get(f"{API}/portal/pymes/{portal['code']}")
    assert closed.status_code == 404
    # quien ya estaba registrado sigue entrando
    assert client.get(f"{API}/portal/requests", headers=portal["a"]).status_code == 200


def test_customers_are_not_team_members(client: TestClient, portal: dict[str, Any]) -> None:
    users = client.get(f"{API}/users", headers=portal["owner"]).json()
    assert all(u["role"] != "customer" for u in users)
    customer_id = portal["token_a"]["user"]["id"]
    promote = client.patch(f"{API}/users/{customer_id}", headers=portal["owner"], json={"role": "owner"})
    assert promote.status_code == 404
    as_customer = client.post(
        f"{API}/users",
        headers=portal["owner"],
        json={"email": "c@prueba.local", "full_name": "C C", "password": PASSWORD, "role": "customer"},
    )
    assert as_customer.status_code == 422


# --------------------------------------------------------------------------- cotizar y enviar


def test_products_are_final_recipes_only(client: TestClient, portal: dict[str, Any]) -> None:
    db: Session = portal["db"]
    db.execute(update(Recipe).where(Recipe.name == "Pie de limón").values(is_final_product=False))
    db.commit()
    names = {p["name"] for p in client.get(f"{API}/portal/products", headers=portal["a"]).json()}
    assert "Empanadas de pino" in names and "Pie de limón" not in names
    assert "Empanadas de queso" in names  # de Aromos; la de Lago no aparece dos veces
    assert len(names) == len(client.get(f"{API}/portal/products", headers=portal["a"]).json())
    not_final = _bad_request(client, portal, portal["recipes"]["Pie de limón"])
    assert not_final.status_code == 422 and not_final.json()["code"] == "product_not_found"


def _bad_request(client: TestClient, portal: dict[str, Any], recipe_id: str) -> Any:
    return client.post(
        f"{API}/portal/requests", headers=portal["a"], json={"lines": [{"recipe_id": recipe_id, "qty": "1"}]}
    )


def test_quote_saved_for_customer_without_internal_data(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    assert req["status"] == "customer_draft" and req["can_send"] and req["can_cancel"]
    q = req["quote"]
    assert q["is_complete"] and q["total_clp"] == q["net_clp"] + q["vat_clp"] and q["vat_pct"] == "19"
    assert q["products"][0]["name"] == "Empanadas de pino" and q["products"][0]["unit_label"] == "docenas"
    assert q["products"][0]["subtotal_clp"] == q["net_clp"]
    raw = client.get(f"{API}/portal/requests/{req['id']}", headers=portal["a"]).text
    for word in INTERNAL:
        assert word.lower() not in raw.lower(), word
    listed = client.get(f"{API}/portal/requests", headers=portal["a"]).json()
    assert [r["id"] for r in listed] == [req["id"]] and listed[0]["total_clp"] == q["total_clp"]
    assert listed[0]["products"] == "2 docenas de Empanadas de pino"
    pdf = client.get(f"{API}/portal/requests/{req['id']}/pdf", headers=portal["a"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Empanadas de pino" in text and "Harina" not in text


def test_unsent_quote_is_invisible_to_the_pyme(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    ids = {o["id"] for o in client.get(f"{API}/orders", headers=portal["owner"]).json()}
    assert req["id"] not in ids
    assert client.get(f"{API}/orders/{req['id']}", headers=portal["owner"]).status_code == 404
    db: Session = portal["db"]
    from app.db.models import Quote

    quote_id = db.scalar(select(Quote.id).where(Quote.order_id == uuid.UUID(req["id"])))
    assert client.get(f"{API}/quotes/{quote_id}", headers=portal["owner"]).status_code == 404


def test_send_then_owner_accepts(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    sent = client.post(f"{API}/portal/requests/{req['id']}/send", headers=portal["a"]).json()
    assert sent["status"] == "requested" and sent["submitted_at"] and not sent["can_send"]
    again = client.post(f"{API}/portal/requests/{req['id']}/send", headers=portal["a"])
    assert again.status_code == 409

    orders = client.get(f"{API}/orders?status=requested", headers=portal["owner"]).json()
    mine = next(o for o in orders if o["id"] == req["id"])
    assert mine["from_customer"] and mine["customer_name"] == "Ana Cliente" and mine["notes"] == "sin cebolla"
    assert mine["last_quote_id"]

    ok = client.post(f"{API}/orders/{req['id']}/accept", headers=portal["owner"], json={"message": "¡Listo!"})
    assert ok.status_code == 200 and ok.json()["status"] == "confirmed"
    quote = client.get(f"{API}/quotes/{mine['last_quote_id']}", headers=portal["owner"]).json()
    assert quote["status"] == "accepted"

    seen = client.get(f"{API}/portal/requests/{req['id']}", headers=portal["a"]).json()
    assert seen["status"] == "confirmed" and seen["owner_message"] == "¡Listo!" and seen["decided_at"]
    assert not seen["can_cancel"]
    assert client.post(f"{API}/portal/requests/{req['id']}/cancel", headers=portal["a"]).status_code == 409
    assert client.post(f"{API}/orders/{req['id']}/accept", headers=portal["owner"], json={}).status_code == 409


def test_owner_rejects_with_message(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Sopaipillas"], "30", "unit")
    client.post(f"{API}/portal/requests/{req['id']}/send", headers=portal["a"])
    out = client.post(f"{API}/orders/{req['id']}/reject", headers=portal["owner"], json={"message": "Sin fecha libre"})
    assert out.json()["status"] == "cancelled"
    seen = client.get(f"{API}/portal/requests/{req['id']}", headers=portal["a"]).json()
    assert seen["status"] == "cancelled" and seen["owner_message"] == "Sin fecha libre"


def test_collaborator_cannot_decide(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Sopaipillas"], "30", "unit")
    client.post(f"{API}/portal/requests/{req['id']}/send", headers=portal["a"])
    collab = login(client, "colaboradora.aromos@demo.local", DEFAULT_DEMO_PASSWORD)
    assert client.post(f"{API}/orders/{req['id']}/accept", headers=collab, json={}).status_code == 403


def test_missing_price_hides_amounts_and_blocks_accept(client: TestClient, portal: dict[str, Any]) -> None:
    """Canapés de salmón lleva eneldo, que no tiene precio: el cliente no ve un total que sería falso."""
    req = _request(client, portal["a"], portal["recipes"]["Canapés de salmón"], "48", "unit")
    assert req["price_pending"] == "missing_prices"
    q = req["quote"]
    assert not q["is_complete"] and q["total_clp"] is None and q["products"][0]["unit_price_clp"] is None
    assert "Eneldo" not in client.get(f"{API}/portal/requests/{req['id']}", headers=portal["a"]).text
    assert client.get(f"{API}/portal/requests/{req['id']}/pdf", headers=portal["a"]).status_code == 409
    client.post(f"{API}/portal/requests/{req['id']}/send", headers=portal["a"])
    blocked = client.post(f"{API}/orders/{req['id']}/accept", headers=portal["owner"], json={})
    assert blocked.status_code == 409 and blocked.json()["code"] == "quote_incomplete"


def test_pyme_without_margin_still_receives_the_request(client: TestClient, portal: dict[str, Any]) -> None:
    code = client.post(f"{API}/pyme/customer-code", headers=portal["lago"]).json()["customer_code"]
    c = _register(client, code, "cliente.lago@prueba.local")
    headers = {"Authorization": f"Bearer {c['access_token']}"}
    products = client.get(f"{API}/portal/products", headers=headers).json()
    assert [p["name"] for p in products] == ["Empanadas de queso"]
    req = _request(client, headers, products[0]["id"])
    assert req["quote"] is None and req["price_pending"] == "margin_required"
    sent = client.post(f"{API}/portal/requests/{req['id']}/send", headers=headers).json()
    assert sent["status"] == "requested"
    assert req["id"] in {o["id"] for o in client.get(f"{API}/orders", headers=portal["lago"]).json()}
    # la otra pyme no la ve, ni el cliente de Aromos
    assert req["id"] not in {o["id"] for o in client.get(f"{API}/orders", headers=portal["owner"]).json()}
    assert client.get(f"{API}/portal/requests/{req['id']}", headers=portal["a"]).status_code == 404
    # ni un producto de otra pyme sirve para cotizar
    assert _bad_request(client, portal, products[0]["id"]).status_code == 422


def test_customers_only_see_their_own_requests(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    for method, path in [
        ("GET", f"/portal/requests/{req['id']}"),
        ("POST", f"/portal/requests/{req['id']}/send"),
        ("POST", f"/portal/requests/{req['id']}/cancel"),
        ("POST", f"/portal/requests/{req['id']}/quote"),
        ("GET", f"/portal/requests/{req['id']}/pdf"),
    ]:
        assert client.request(method, API + path, headers=portal["b"]).status_code == 404, path
    assert client.get(f"{API}/portal/requests", headers=portal["b"]).json() == []


def test_customer_cancels_before_answer_and_requote(client: TestClient, portal: dict[str, Any]) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    again = client.post(f"{API}/portal/requests/{req['id']}/quote", headers=portal["a"]).json()
    assert again["quote"]["version"] == 2
    out = client.post(f"{API}/portal/requests/{req['id']}/cancel", headers=portal["a"]).json()
    assert out["status"] == "cancelled" and not out["can_send"]


def test_staff_cannot_set_portal_statuses(client: TestClient, portal: dict[str, Any]) -> None:
    orders = client.get(f"{API}/orders", headers=portal["owner"]).json()
    resp = client.patch(f"{API}/orders/{orders[0]['id']}", headers=portal["owner"], json={"status": "requested"})
    assert resp.status_code == 422


def test_customer_extract_uses_only_products(
    client: TestClient, portal: dict[str, Any], fake_llm: FakeProvider
) -> None:
    fake_llm.responses.append(
        '{"guests": 20, "event_date_text": "el sábado", "items": [{"name": "empanadas de pino", "quantity": 3, '
        '"unit": "docena"}]}'
    )
    out = client.post(
        f"{API}/portal/extract", headers=portal["a"], json={"text": "3 docenas de empanadas de pino para el sábado"}
    ).json()
    assert out["lines"][0]["recipe_name"] == "Empanadas de pino" and out["event_date"]
    assert not client.get(f"{API}/portal/requests", headers=portal["a"]).json()  # leer no guarda


def test_extract_quota_per_customer() -> None:
    user = uuid.uuid4()
    limit = get_settings().portal_extract_per_hour
    for i in range(limit):
        service.check_extract_quota(user, now=1000.0 + i)
    with pytest.raises(ProblemError) as exc:
        service.check_extract_quota(user, now=1000.0 + limit)
    assert exc.value.status == 429
    service.check_extract_quota(user, now=1000.0 + 3601)  # pasada la hora, vuelve a poder
    service.check_extract_quota(uuid.uuid4(), now=1000.0)  # otro cliente no se ve afectado


def test_order_table_keeps_customer_link(portal: dict[str, Any], client: TestClient) -> None:
    req = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    db: Session = portal["db"]
    order = db.get(Order, uuid.UUID(req["id"]))
    assert order is not None and str(order.customer_user_id) == portal["token_a"]["user"]["id"]
    assert order.customer_contact == "cliente.a@prueba.local"


# --------------------------------------------------------------------------- varias pymes (el cliente elige)


def test_customer_chooses_the_pyme_and_each_owner_sees_only_theirs(client: TestClient, portal: dict[str, Any]) -> None:
    client.post(f"{API}/pyme/customer-code", headers=portal["lago"])  # Lago abre su portal
    pymes = {p["name"]: p for p in client.get(f"{API}/portal/pymes", headers=portal["a"]).json()}
    assert pymes["Cocina Los Aromos (demo)"]["joined"] and not pymes["Banquetería del Lago (demo)"]["joined"]
    lago_id = pymes["Banquetería del Lago (demo)"]["id"]

    products = client.get(f"{API}/portal/products", headers=portal["a"], params={"pyme_id": lago_id}).json()
    assert [p["name"] for p in products] == ["Empanadas de queso"]  # solo los de Lago
    body = {"pyme_id": lago_id, "lines": [{"recipe_id": products[0]["id"], "qty": "3", "unit": "dozen"}]}
    to_lago = client.post(f"{API}/portal/requests", headers=portal["a"], json=body).json()
    assert to_lago["pyme_name"] == "Banquetería del Lago (demo)" and to_lago["price_pending"] == "margin_required"
    client.post(f"{API}/portal/requests/{to_lago['id']}/send", headers=portal["a"])
    to_aromos = _request(client, portal["a"], portal["recipes"]["Empanadas de pino"])
    client.post(f"{API}/portal/requests/{to_aromos['id']}/send", headers=portal["a"])

    # Mis cotizaciones junta las dos pymes
    mine = {r["id"]: r["pyme_name"] for r in client.get(f"{API}/portal/requests", headers=portal["a"]).json()}
    assert mine == {to_lago["id"]: "Banquetería del Lago (demo)", to_aromos["id"]: "Cocina Los Aromos (demo)"}
    # Cada dueña ve solo la que le enviaron, con el contacto del cliente
    lago_orders = {o["id"]: o for o in client.get(f"{API}/orders?status=requested", headers=portal["lago"]).json()}
    aromos_orders = {o["id"] for o in client.get(f"{API}/orders?status=requested", headers=portal["owner"]).json()}
    assert set(lago_orders) == {to_lago["id"]} and aromos_orders == {to_aromos["id"]}
    assert lago_orders[to_lago["id"]]["customer_contact"] == "cliente.a@prueba.local"
    # El cliente ahora figura como de Lago, y su cuenta allá entra con la misma contraseña
    pymes = {p["name"]: p for p in client.get(f"{API}/portal/pymes", headers=portal["a"]).json()}
    assert pymes["Banquetería del Lago (demo)"]["joined"]
    assert (
        client.post(f"{API}/auth/login", json={"email": "cliente.a@prueba.local", "password": PASSWORD}).status_code
        == 200
    )
    # Otro cliente no ve la solicitud enviada a Lago
    assert client.get(f"{API}/portal/requests/{to_lago['id']}", headers=portal["b"]).status_code == 404


def test_cannot_quote_to_a_pyme_with_closed_portal(client: TestClient, portal: dict[str, Any], db: Session) -> None:
    lago_id = db.scalar(select(Pyme.id).where(Pyme.name == "Banquetería del Lago (demo)"))
    names = {p["name"] for p in client.get(f"{API}/portal/pymes", headers=portal["a"]).json()}
    assert "Banquetería del Lago (demo)" not in names  # portal cerrado: no aparece
    resp = client.get(f"{API}/portal/products", headers=portal["a"], params={"pyme_id": str(lago_id)})
    assert resp.status_code == 404 and resp.json()["code"] == "pyme_not_available"
    recipe = db.scalar(select(Recipe.id).where(Recipe.pyme_id == lago_id))
    body = {"pyme_id": str(lago_id), "lines": [{"recipe_id": str(recipe), "qty": "1"}]}
    assert client.post(f"{API}/portal/requests", headers=portal["a"], json=body).status_code == 404


def test_register_from_directory_and_email_rules(client: TestClient, portal: dict[str, Any]) -> None:
    directory = client.get(f"{API}/portal/directory").json()
    assert [p["name"] for p in directory] == ["Cocina Los Aromos (demo)"]  # solo las con portal abierto
    ok = client.post(
        f"{API}/portal/register",
        json={
            "pyme_id": directory[0]["id"],
            "full_name": "Dora Directorio",
            "email": "dora@prueba.local",
            "password": PASSWORD,
        },
    )
    assert ok.status_code == 201 and ok.json()["user"]["role"] == "customer"
    again = client.post(
        f"{API}/portal/register",
        json={"code": portal["code"], "full_name": "Ana", "email": "cliente.a@prueba.local", "password": PASSWORD},
    )
    assert again.status_code == 409 and again.json()["title"] == "Ya tienes una cuenta de cliente"
    staff = client.post(
        f"{API}/auth/register",
        json={"pyme_name": "Otra", "full_name": "Ana", "email": "cliente.a@prueba.local", "password": PASSWORD},
    )
    assert staff.status_code == 409  # un correo de cliente no se usa para una cuenta de pyme
    no_pyme = client.post(
        f"{API}/portal/register", json={"full_name": "Sin Pyme", "email": "x@prueba.local", "password": PASSWORD}
    )
    assert no_pyme.status_code == 422

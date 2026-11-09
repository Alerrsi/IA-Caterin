import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.tenancy import TenantViolationError, open_tenant_session
from app.db.enums import BaseUnit
from app.db.models import Ingredient
from tests.helpers import PASSWORD, Tenant, assert_isolated, login, register

API = "/api/v1"


@pytest.fixture
def two(client: TestClient) -> tuple[Tenant, Tenant]:
    return register(client, "Pyme A", "a@pyme.cl"), register(client, "Pyme B", "b@pyme.cl")


def _collaborator(client: TestClient, owner: Tenant, email: str = "colab@pyme.cl") -> tuple[str, dict[str, str]]:
    resp = client.post(
        f"{API}/users",
        headers=owner.headers,
        json={"email": email, "full_name": "Colaboradora", "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"], login(client, email)


# --------------------------------------------------------------------------- registro y login


def test_register_login_me_flow(client: TestClient) -> None:
    t = register(client, "Cocina Prueba", "Duena@Pyme.cl")
    assert client.cookies.get("caterin_refresh")
    me = client.get(f"{API}/auth/me", headers=t.headers)
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "duena@pyme.cl"  # se normaliza a minúsculas
    assert me.json()["user"]["role"] == "owner"
    assert me.json()["pyme"]["vat_pct"] == "19.00"
    assert login(client, "DUENA@pyme.cl")


def test_register_rejects_duplicate_email_and_weak_password(client: TestClient) -> None:
    register(client, "Pyme A", "a@pyme.cl")
    dup = client.post(
        f"{API}/auth/register",
        json={"pyme_name": "Otra", "full_name": "X Y", "email": "a@pyme.cl", "password": PASSWORD},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "email_taken"
    for bad in ("corta", "1234567890"):
        resp = client.post(
            f"{API}/auth/register",
            json={"pyme_name": "Otra", "full_name": "X Y", "email": "z@pyme.cl", "password": bad},
        )
        assert resp.status_code == 422
        assert resp.json()["errors"][0]["field"] == "password"


def test_wrong_password_is_generic_and_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    register(client, "Pyme A", "a@pyme.cl")
    monkeypatch.setattr(get_settings(), "login_max_attempts", 3)
    for _ in range(3):
        resp = client.post(f"{API}/auth/login", json={"email": "a@pyme.cl", "password": "equivocada-123"})
        assert resp.status_code == 401
        assert resp.json()["title"] == "Correo o contraseña incorrectos"
    blocked = client.post(f"{API}/auth/login", json={"email": "a@pyme.cl", "password": PASSWORD})
    assert blocked.status_code == 429
    # un correo que no existe responde igual que una contraseña mala
    monkeypatch.setattr(get_settings(), "login_max_attempts", 10)
    ghost = client.post(f"{API}/auth/login", json={"email": "nadie@pyme.cl", "password": PASSWORD})
    assert ghost.status_code == 401
    assert ghost.json()["title"] == "Correo o contraseña incorrectos"


# --------------------------------------------------------------------------- tokens


def test_refresh_rotates_and_detects_reuse(client: TestClient) -> None:
    register(client, "Pyme A", "a@pyme.cl")
    first = client.cookies.get("caterin_refresh")
    resp = client.post(f"{API}/auth/refresh")
    assert resp.status_code == 200
    second = client.cookies.get("caterin_refresh")
    assert second and second != first
    # reutilizar el refresh viejo revoca toda la sesión (incluido el nuevo)
    client.cookies.set("caterin_refresh", first, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401
    client.cookies.set("caterin_refresh", second, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_logout_revokes_refresh(client: TestClient) -> None:
    register(client, "Pyme A", "a@pyme.cl")
    token = client.cookies.get("caterin_refresh")
    assert client.post(f"{API}/auth/logout").status_code == 204
    client.cookies.set("caterin_refresh", token, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def _forge(**claims: object) -> dict[str, str]:
    base = {"type": "access", "role": "owner", "exp": datetime.now(UTC) + timedelta(minutes=5)}
    base.update(claims)
    token = jwt.encode(base, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_invalid_tokens_are_rejected(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, b = two
    cases = {
        "sin token": {},
        "basura": {"Authorization": "Bearer abc.def.ghi"},
        "vencido": _forge(sub=a.user_id, pyme_id=a.pyme_id, exp=datetime.now(UTC) - timedelta(seconds=1)),
        "usuaria de A con pyme de B": _forge(sub=a.user_id, pyme_id=b.pyme_id),
        "tipo incorrecto": _forge(sub=a.user_id, pyme_id=a.pyme_id, type="refresh"),
        "firma ajena": {
            "Authorization": "Bearer "
            + jwt.encode(
                {"sub": a.user_id, "pyme_id": a.pyme_id, "type": "access", "role": "owner", "exp": 9999999999},
                "otra-clave-otra-clave-otra-clave-otra",
                algorithm="HS256",
            )
        },
    }
    for name, headers in cases.items():
        resp = client.get(f"{API}/auth/me", headers=headers)
        assert resp.status_code == 401, name
        assert resp.headers["content-type"].startswith("application/problem+json")


# --------------------------------------------------------------------------- roles y usuarias


def test_collaborator_permissions(client: TestClient) -> None:
    owner = register(client, "Pyme A", "a@pyme.cl")
    _, colab = _collaborator(client, owner)
    assert client.get(f"{API}/pyme", headers=colab).status_code == 200
    assert client.patch(f"{API}/pyme", headers=colab, json={"default_margin_pct": "30"}).status_code == 403
    assert client.get(f"{API}/users", headers=colab).status_code == 403
    resp = client.patch(f"{API}/pyme", headers=owner.headers, json={"default_margin_pct": "30"})
    assert resp.status_code == 200
    assert resp.json()["default_margin_pct"] == "30.00"


def test_last_owner_and_self_protection(client: TestClient) -> None:
    owner = register(client, "Pyme A", "a@pyme.cl")
    path = f"{API}/users/{owner.user_id}"
    assert client.patch(path, headers=owner.headers, json={"role": "collaborator"}).json()["code"] == "last_owner"
    assert client.delete(path, headers=owner.headers).status_code == 409


def test_deactivated_user_loses_access(client: TestClient) -> None:
    owner = register(client, "Pyme A", "a@pyme.cl")
    colab_id, colab = _collaborator(client, owner)
    assert client.get(f"{API}/auth/me", headers=colab).status_code == 200
    assert client.delete(f"{API}/users/{colab_id}", headers=owner.headers).status_code == 204
    assert client.get(f"{API}/auth/me", headers=colab).status_code == 401
    resp = client.post(f"{API}/auth/login", json={"email": "colab@pyme.cl", "password": PASSWORD})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- aislamiento entre pymes


def test_users_are_isolated_between_pymes(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, b = two
    colab_b, _ = _collaborator(client, b, "colab.b@pyme.cl")
    listed = {u["email"] for u in client.get(f"{API}/users", headers=a.headers).json()}
    assert listed == {"a@pyme.cl"}
    for target in (b.user_id, colab_b):
        assert_isolated(client, a, "PATCH", f"{API}/users/{target}", json={"full_name": "Intrusa"})
        assert_isolated(client, a, "DELETE", f"{API}/users/{target}")
    assert client.get(f"{API}/pyme", headers=a.headers).json()["name"] == "Pyme A"


def test_tenant_session_filters_reads_and_blocks_foreign_writes(client: TestClient, two: tuple[Tenant, Tenant]) -> None:
    a, b = two
    pa, pb = uuid.UUID(a.pyme_id), uuid.UUID(b.pyme_id)
    with open_tenant_session(pb) as sb:
        sb.add(Ingredient(name="Harina B", base_unit=BaseUnit.GRAM))  # pyme_id se asigna solo
        sb.commit()
    with open_tenant_session(pa, uuid.UUID(a.user_id)) as sa:
        sa.add(Ingredient(name="Harina A", base_unit=BaseUnit.GRAM))
        sa.commit()
        names = sa.scalars(select(Ingredient.name)).all()
        assert names == ["Harina A"]
        own = sa.scalars(select(Ingredient)).one()
        assert own.created_by == uuid.UUID(a.user_id)
        sa.add(Ingredient(pyme_id=pb, name="Colada", base_unit=BaseUnit.GRAM))
        with pytest.raises(TenantViolationError):
            sa.flush()

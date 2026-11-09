"""Helpers de pruebas reutilizables por todas las tareas (aislamiento entre pymes)."""

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

PASSWORD = "clave-segura-de-prueba"


@dataclass
class Tenant:
    headers: dict[str, str]
    user_id: str
    pyme_id: str
    email: str


def register(client: TestClient, pyme: str, email: str, password: str = PASSWORD) -> Tenant:
    resp = client.post(
        "/api/v1/auth/register",
        json={"pyme_name": pyme, "full_name": f"Dueña {pyme}", "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return Tenant(
        headers={"Authorization": f"Bearer {body['access_token']}"},
        user_id=body["user"]["id"],
        pyme_id=body["pyme"]["id"],
        email=email,
    )


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def assert_isolated(client: TestClient, intruder: Tenant, method: str, path: str, json: Any = None) -> None:
    """Una pyme que pide un recurso de otra recibe 404 (no 403, para no revelar que existe)."""
    resp = client.request(method, path, headers=intruder.headers, json=json)
    assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}: {resp.text}"

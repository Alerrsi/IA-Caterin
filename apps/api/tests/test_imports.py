import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from tests.helpers import Tenant, assert_isolated, register
from tests.test_inventory import new_ingredient
from tests.test_suppliers_recipes import new_price, new_supplier

API = "/api/v1"


@pytest.fixture
def a(client: TestClient) -> Tenant:
    return register(client, "Pyme A", "a@pyme.cl")


def upload(client: TestClient, t: Tenant, kind: str, name: str, data: bytes) -> dict[str, object]:
    resp = client.post(f"{API}/imports/{kind}/preview", headers=t.headers, files={"file": (name, data)})
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def ingredient_csv(rows: int = 30, bad_rows: tuple[int, ...] = (5, 17)) -> bytes:
    lines = ["Nombre;Unidad;Stock;Stock mínimo;Merma %;Categoría"]
    for i in range(rows):
        if i == bad_rows[0]:
            lines.append(f"Insumo {i};tazas;2;;;Abarrotes")  # unidad desconocida
        elif i == bad_rows[1]:
            lines.append(f"Insumo {i};kg;mucho;;;Abarrotes")  # número inválido
        else:
            lines.append(f"Insumo {i};kg;2,5;1;3;Abarrotes")
    return "\n".join(lines).encode("latin-1")  # como lo guarda Excel en Windows


def test_ingredient_import_preview_confirm_undo(client: TestClient, a: Tenant) -> None:
    preview = upload(client, a, "ingredients", "insumos.csv", ingredient_csv())
    assert preview["total_rows"] == 30
    assert len(preview["valid"]) == 28  # type: ignore[arg-type]
    errors = preview["errors"]
    assert [(e["row"], e["field"]) for e in errors] == [(7, "unidad"), (19, "stock")]  # type: ignore[union-attr]
    first = preview["valid"][0]  # type: ignore[index]
    assert first["stock_qty"] == "2500.000"
    assert first["min_stock_qty"] == "1000.000"
    assert first["base_unit"] == "g"

    confirm = client.post(f"{API}/imports/ingredients/confirm", headers=a.headers, json={"rows": preview["valid"]})
    assert confirm.status_code == 201
    batch = confirm.json()["import_batch_id"]
    items = client.get(f"{API}/ingredients?limit=100", headers=a.headers).json()["items"]
    assert len(items) == 28
    # volver a importar la misma planilla avisa que ya existen
    again = upload(client, a, "ingredients", "insumos.csv", ingredient_csv())
    assert {e["message"] for e in again["errors"]} >= {"Ya tienes un insumo con ese nombre"}  # type: ignore[union-attr]
    resend = client.post(f"{API}/imports/ingredients/confirm", headers=a.headers, json={"rows": preview["valid"]})
    assert resend.status_code == 409

    undo = client.delete(f"{API}/imports/{batch}", headers=a.headers)
    assert undo.status_code == 200
    assert undo.json()["ingredients_deleted"] == 28
    assert client.get(f"{API}/ingredients", headers=a.headers).json()["items"] == []


def test_undo_is_blocked_when_imported_data_is_used(client: TestClient, a: Tenant) -> None:
    preview = upload(client, a, "ingredients", "i.csv", b"nombre,unidad,stock\nHarina,kg,10\n")
    batch = client.post(f"{API}/imports/ingredients/confirm", headers=a.headers, json={"rows": preview["valid"]})
    flour = client.get(f"{API}/ingredients", headers=a.headers).json()["items"][0]
    client.post(
        f"{API}/recipes",
        headers=a.headers,
        json={"name": "Masa", "yield_qty": "1", "lines": [{"ingredient_id": flour["id"], "qty": "100"}]},
    )
    resp = client.delete(f"{API}/imports/{batch.json()['import_batch_id']}", headers=a.headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Harina"


def test_excel_import(client: TestClient, a: Tenant) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Nombre", "Unidad", "Stock"])
    ws.append(["Huevo", "unidad", 90])
    ws.append(["Crema de leche", "litros", 1.5])
    buf = io.BytesIO()
    wb.save(buf)
    preview = upload(client, a, "ingredients", "insumos.xlsx", buf.getvalue())
    assert [(r["name"], r["base_unit"], r["stock_qty"]) for r in preview["valid"]] == [  # type: ignore[union-attr]
        ("Huevo", "unit", "90.000"),
        ("Crema de leche", "ml", "1500.000"),
    ]


def test_price_import_creates_suppliers_and_undo_restores_previous(client: TestClient, a: Tenant) -> None:
    flour = new_ingredient(client, a, "Harina sin polvos")
    milk = new_ingredient(client, a, "Leche", "ml")
    molino = new_supplier(client, a, "Molino")
    previous = new_price(client, a, flour["id"], molino["id"])
    csv = (
        "insumo;proveedor;presentacion;cantidad;unidad;precio;incluye_iva;fecha\n"
        "harina sin polvos;Molino;saco 25 kg;25;kg;$19.990;si;05-11-2026\n"
        "Leche;Lechería Nueva;caja 1 L;1;l;1.090;no;2026-11-05\n"
        "Chocolate;Molino;barra;1;kg;5000;si;05-11-2026\n"
        "Leche;Lechería Nueva;caja;1;kg;1000;si;05-11-2026\n"
        "Leche;Lechería Nueva;caja;1;l;10,5;si;31-02-2026\n"
    ).encode()
    preview = upload(client, a, "prices", "precios.csv", csv)
    valid = preview["valid"]
    assert [(r["ingredient_name"], r["price_clp"], r["supplier_is_new"]) for r in valid] == [  # type: ignore[union-attr]
        ("Harina sin polvos", 19990, False),
        ("Leche", 1090, True),
    ]
    fields = sorted((e["row"], e["field"]) for e in preview["errors"])  # type: ignore[union-attr]
    assert fields == [(4, "insumo"), (5, "unidad"), (6, "fecha"), (6, "precio")]
    resp = client.post(f"{API}/imports/prices/confirm", headers=a.headers, json={"rows": valid, "source": "csv"})
    assert resp.status_code == 201
    assert resp.json()["suppliers_created"] == 1
    current = client.get(f"{API}/prices?ingredient_id={flour['id']}", headers=a.headers).json()
    assert [p["price_clp"] for p in current] == [19990]
    milk_prices = client.get(f"{API}/prices?ingredient_id={milk['id']}", headers=a.headers).json()
    assert milk_prices[0]["includes_vat"] is False
    assert milk_prices[0]["package_qty"] == "1000.000"

    client.delete(f"{API}/imports/{resp.json()['import_batch_id']}", headers=a.headers)
    restored = client.get(f"{API}/prices?ingredient_id={flour['id']}", headers=a.headers).json()
    assert [p["id"] for p in restored] == [previous["id"]]


def test_file_limits_and_templates(client: TestClient, a: Tenant) -> None:
    big = b"nombre;unidad\n" + b"x" * (5 * 1024 * 1024)
    resp = client.post(f"{API}/imports/ingredients/preview", headers=a.headers, files={"file": ("a.csv", big)})
    assert resp.status_code == 413
    fake = client.post(f"{API}/imports/ingredients/preview", headers=a.headers, files={"file": ("a.xlsx", b"hola")})
    assert fake.status_code == 415
    empty = client.post(f"{API}/imports/ingredients/preview", headers=a.headers, files={"file": ("a.csv", b"\n\n")})
    assert empty.status_code == 422
    tpl = client.get(f"{API}/imports/templates/ingredients.csv")
    assert tpl.status_code == 200
    assert tpl.text.lstrip("﻿").startswith("nombre;unidad")


def test_imports_are_isolated(client: TestClient, a: Tenant) -> None:
    b = register(client, "Pyme B", "b@pyme.cl")
    preview = upload(client, a, "ingredients", "i.csv", b"nombre,unidad,stock\nHarina,kg,10\n")
    batch = client.post(f"{API}/imports/ingredients/confirm", headers=a.headers, json={"rows": preview["valid"]})
    assert_isolated(client, b, "DELETE", f"{API}/imports/{batch.json()['import_batch_id']}")
    # B ve el insumo de A como inexistente en su vista previa de precios
    csv = b"insumo;proveedor;cantidad;precio\nHarina;Molino;1000;1000\n"
    assert upload(client, b, "prices", "p.csv", csv)["valid"] == []

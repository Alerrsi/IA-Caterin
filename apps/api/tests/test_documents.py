"""Documentos del nivel 2: subida, fragmentación, búsqueda híbrida (FTS + pgvector) y aislamiento entre pymes."""

import io
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embeddings import DisabledEmbeddings, FakeEmbeddings, get_embeddings
from app.core.tenancy import open_tenant_session
from app.db.models import DocumentChunk
from app.modules.documents import service
from app.modules.documents.parsing import CHUNK_CHARS, DocumentParseError, parse, split_text
from tests.helpers import PASSWORD, Tenant, login, register

API = "/api/v1"
CONDITIONS = (
    "Condiciones de Harinas Cautín\n\n"
    "Pedido mínimo de $30.000. Despachan martes y jueves en Temuco y Padre Las Casas.\n\n"
    "Pago por transferencia a 30 días para clientes frecuentes. Las devoluciones se aceptan hasta 48 horas "
    "después de la entrega, con la boleta."
)


@pytest.fixture(autouse=True)
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "storage_dir", tmp_path)
    return tmp_path


@pytest.fixture
def owner(client: TestClient) -> Tenant:
    return register(client, "Cocina Uno", "uno@demo.local")


def upload(client: TestClient, t: Tenant, name: str, data: bytes) -> dict:  # type: ignore[type-arg]
    r = client.post(f"{API}/documents", headers=t.headers, files={"file": (name, io.BytesIO(data))})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


@pytest.fixture
def sessions() -> Iterator[list[Session]]:
    opened: list[Session] = []
    yield opened
    for s in opened:
        s.close()


def tenant(t: Tenant, opened: list[Session]) -> Session:
    s = open_tenant_session(uuid.UUID(t.pyme_id))
    opened.append(s)
    return s


# --------------------------------------------------------------------------- unitarias


def test_split_text_keeps_paragraphs_and_cuts_long_ones() -> None:
    chunks = split_text("Uno.\n\nDos.\n\n" + "palabra " * 300, {"page": 1})
    assert chunks[0].text.startswith("Uno.") and all(len(c.text) <= CHUNK_CHARS for c in chunks)
    assert all(c.meta == {"page": 1} for c in chunks) and len(chunks) >= 3


def test_parse_csv_xlsx_and_rejects_unknown() -> None:
    csv_chunks = parse("precios.csv", "insumo;precio\nharina;1200\nazúcar;1500\n".encode())
    assert csv_chunks[0].meta == {"rows": "2-3"} and "harina | 1200" in csv_chunks[0].text
    wb = Workbook()
    wb.active.append(["insumo", "precio"])  # type: ignore[union-attr]
    wb.active.append(["sal", 500])  # type: ignore[union-attr]
    buf = io.BytesIO()
    wb.save(buf)
    xlsx = parse("lista.xlsx", buf.getvalue())
    assert xlsx[0].meta["sheet"] and "sal | 500" in xlsx[0].text
    with pytest.raises(DocumentParseError):
        parse("virus.exe", b"MZ")


def test_fake_embeddings_are_normalized_and_close_for_shared_words() -> None:
    a, b, c = FakeEmbeddings().embed(["pedido mínimo harina", "harina pedido mínimo", "brochetas de fruta"])
    dot = lambda x, y: sum(p * q for p, q in zip(x, y, strict=True))  # noqa: E731
    assert abs(dot(a, a) - 1) < 1e-9 and dot(a, b) > dot(a, c)


# --------------------------------------------------------------------------- integración


def test_upload_list_and_delete(client: TestClient, owner: Tenant, storage: Path) -> None:
    doc = upload(client, owner, "condiciones.txt", CONDITIONS.encode())
    assert doc["index_status"] == "indexed" and doc["chunks"] >= 1 and doc["has_embeddings"] is True
    assert any(storage.rglob("*.txt"))
    listed = client.get(f"{API}/documents", headers=owner.headers).json()
    assert [d["id"] for d in listed] == [doc["id"]]
    assert client.delete(f"{API}/documents/{doc['id']}", headers=owner.headers).status_code == 204
    assert client.get(f"{API}/documents", headers=owner.headers).json() == []
    assert not any(storage.rglob("*.txt"))


def test_rejects_duplicate_unsupported_empty_and_large(
    client: TestClient, owner: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload(client, owner, "a.txt", CONDITIONS.encode())
    post = lambda name, data: client.post(  # noqa: E731
        f"{API}/documents", headers=owner.headers, files={"file": (name, io.BytesIO(data))}
    )
    assert post("b.txt", CONDITIONS.encode()).status_code == 409
    assert post("x.exe", b"MZ").status_code == 415
    assert post("vacio.txt", b"   ").status_code == 422
    monkeypatch.setattr(get_settings(), "document_max_upload_mb", 0)
    assert post("grande.txt", b"x" * 10).status_code == 413


def test_collaborator_cannot_upload(client: TestClient, owner: Tenant) -> None:
    r = client.post(
        f"{API}/users",
        headers=owner.headers,
        json={"email": "colab@demo.local", "full_name": "Colab", "password": PASSWORD, "role": "collaborator"},
    )
    assert r.status_code == 201, r.text
    colab = login(client, "colab@demo.local")
    files = {"file": ("a.txt", io.BytesIO(b"hola"))}
    assert client.post(f"{API}/documents", headers=colab, files=files).status_code == 403
    assert client.get(f"{API}/documents", headers=colab).status_code == 200


def test_hybrid_search_finds_and_cites(client: TestClient, owner: Tenant, sessions: list[Session]) -> None:
    upload(client, owner, "condiciones.txt", CONDITIONS.encode())
    upload(client, owner, "precios.csv", "insumo;precio\nharina;1200\nazúcar;1500\n".encode())
    s = tenant(owner, sessions)
    hits = service.search(s, FakeEmbeddings(), "¿Cuál es el pedido mínimo de Harinas Cautín?", 4, 0.3)
    assert hits and "Pedido mínimo" in hits[0].text and hits[0].text_match
    assert hits[0].citation() == "condiciones.txt"
    csv_hit = service.search(s, FakeEmbeddings(), "precio del azúcar", 4, 0.3)
    assert any(h.filename == "precios.csv" and "filas 2-3" in h.citation() for h in csv_hit)
    assert service.search(s, FakeEmbeddings(), "zzzz qqqq", 4, 0.99) == []


def test_other_pyme_never_finds_my_documents(client: TestClient, owner: Tenant, sessions: list[Session]) -> None:
    upload(client, owner, "condiciones.txt", CONDITIONS.encode())
    other = register(client, "Cocina Dos", "dos@demo.local")
    assert client.get(f"{API}/documents", headers=other.headers).json() == []
    s = tenant(other, sessions)
    assert service.search(s, FakeEmbeddings(), "pedido mínimo Harinas Cautín", 4, 0.0) == []
    assert not service.has_documents(s)
    doc_id = client.get(f"{API}/documents", headers=owner.headers).json()[0]["id"]
    assert client.delete(f"{API}/documents/{doc_id}", headers=other.headers).status_code == 404


def test_without_embeddings_document_is_still_searchable_by_text(
    client: TestClient, owner: Tenant, sessions: list[Session]
) -> None:
    client.app.dependency_overrides[get_embeddings] = DisabledEmbeddings  # type: ignore[attr-defined]
    try:
        doc = upload(client, owner, "condiciones.txt", CONDITIONS.encode())
    finally:
        client.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    assert doc["has_embeddings"] is False and doc["index_status"] == "indexed"
    s = tenant(owner, sessions)
    assert s.scalars(select(DocumentChunk.embedding)).first() is None
    hits = service.search(s, DisabledEmbeddings(), "devoluciones con boleta", 4, 0.5)
    assert hits and "devoluciones" in hits[0].text


def test_parse_pdf_keeps_page_numbers() -> None:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Politica de anulaciones: hasta 72 horas antes del evento.")
    c.showPage()
    c.drawString(72, 720, "Recargo por despacho fuera de Temuco.")
    c.save()
    chunks = parse("politicas.pdf", buf.getvalue())
    assert [c.meta["page"] for c in chunks] == [1, 2] and "72 horas" in chunks[0].text
    with pytest.raises(DocumentParseError):
        parse("roto.pdf", b"%PDF-1.4 basura")


def test_reindex_turns_old_chunks_into_sentences(client: TestClient, owner: Tenant, sessions: list[Session]) -> None:
    doc_id = uuid.UUID(upload(client, owner, "condiciones.txt", CONDITIONS.encode())["id"])
    db = tenant(owner, sessions)
    # Simula un documento subido antes de sentence-v1: un solo fragmento largo, sin `unit` en meta.
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc_id)))
    for c in chunks[1:]:
        db.delete(c)
    chunks[0].text, chunks[0].meta = CONDITIONS, {}
    db.commit()
    assert service.needs_reindex(db, doc_id)
    out = service.reindex(db, FakeEmbeddings(), doc_id)
    assert out.chunks > 1 and out.has_embeddings and not service.needs_reindex(db, doc_id)
    metas = list(db.scalars(select(DocumentChunk.meta).where(DocumentChunk.document_id == doc_id)))
    assert all(m["unit"] == "sentence-v1" for m in metas)
    intruder = register(client, "Otra Pyme", "otra@demo.local")
    with pytest.raises(Exception, match="documento"):
        service.reindex(tenant(intruder, sessions), FakeEmbeddings(), doc_id)  # otra pyme no lo ve

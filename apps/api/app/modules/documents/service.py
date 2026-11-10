"""Documentos para el nivel 2 del asistente: subida, indexación y búsqueda híbrida (ADR-005).

Búsqueda: texto completo de Postgres (configuración `spanish`) + similitud de vectores en pgvector,
fusionadas por Reciprocal Rank Fusion. Todo pasa por la sesión de tenant: una pyme nunca ve fragmentos
de otra. Si los embeddings no están disponibles, el documento igual queda buscable por texto.
"""

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.data_version import bump
from app.core.embeddings import EmbeddingProvider, EmbeddingsUnavailableError
from app.core.errors import ProblemError, not_found
from app.db.enums import DataDomain, IndexStatus
from app.db.models import Document, DocumentChunk
from app.modules.assistant.recognizer import normalize_question as normalize
from app.modules.documents.parsing import (
    INDEX_UNIT,
    MIME,
    Chunk,
    DocumentParseError,
    embedding_text,
    parse,
    to_sentences,
)
from app.modules.documents.schemas import DocumentOut

logger = logging.getLogger(__name__)

RRF_K = 60
CANDIDATES = 20
EMBED_BATCH = 16


@dataclass(frozen=True)
class Hit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    text: str
    meta: dict[str, Any]
    score: float
    similarity: float | None
    text_match: bool

    def citation(self) -> str:
        where = []
        if "page" in self.meta:
            where.append(f"pág. {self.meta['page']}")
        if "sheet" in self.meta:
            where.append(f"hoja {self.meta['sheet']}")
        if "rows" in self.meta:
            where.append(f"filas {self.meta['rows']}")
        return f"{self.filename}" + (f", {', '.join(where)}" if where else "")


def _storage(pyme_id: uuid.UUID, doc_id: uuid.UUID, ext: str) -> Path:
    return get_settings().storage_dir / "docs" / str(pyme_id) / f"{doc_id}{ext}"


def _out(db: Session, doc: Document) -> DocumentOut:
    n, with_vec = db.execute(
        select(func.count(), func.count(DocumentChunk.embedding)).where(DocumentChunk.document_id == doc.id)
    ).one()
    return DocumentOut.model_validate(doc).model_copy(update={"chunks": n, "has_embeddings": with_vec > 0})


def list_documents(db: Session) -> list[DocumentOut]:
    return [_out(db, d) for d in db.scalars(select(Document).order_by(Document.created_at.desc()))]


def upload(db: Session, emb: EmbeddingProvider, filename: str, data: bytes) -> DocumentOut:
    name = Path(filename).name[:200] or "documento"
    ext = Path(name).suffix.lower()
    if ext not in MIME:
        raise ProblemError(415, "unsupported_document", "Tipo de documento no permitido", "Usa PDF, Excel, CSV o TXT.")
    sha = hashlib.sha256(data).hexdigest()
    if db.scalar(select(Document.id).where(Document.sha256 == sha)) is not None:
        raise ProblemError(409, "document_exists", "Ya subiste este documento")
    try:
        chunks = to_sentences(parse(name, data))
    except DocumentParseError as exc:
        raise ProblemError(422, "unreadable_document", "No pudimos leer el documento", str(exc)) from exc
    if not chunks:
        raise ProblemError(422, "empty_document", "El documento no tiene texto que se pueda leer")

    doc_id = uuid.uuid4()
    path = _storage(db.info["pyme_id"], doc_id, ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    settings = get_settings()
    doc = Document(
        id=doc_id,
        filename=name,
        mime_type=MIME[ext],
        sha256=sha,
        size_bytes=len(data),
        storage_path=str(path.relative_to(settings.storage_dir)),
        index_status=IndexStatus.PENDING,
    )
    db.add(doc)
    _index(db, emb, doc, chunks)
    db.commit()
    return _out(db, doc)


def _index(db: Session, emb: EmbeddingProvider, doc: Document, chunks: list[Chunk]) -> None:
    vectors: list[list[float] | None] = [None] * len(chunks)
    try:
        for start in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[start : start + EMBED_BATCH]
            for i, v in enumerate(emb.embed([embedding_text(c) for c in batch])):
                vectors[start + i] = v
    except EmbeddingsUnavailableError:
        logger.warning("document_embeddings_unavailable", extra={"document_id": str(doc.id)})
        vectors = [None] * len(chunks)
    for i, (chunk, vec) in enumerate(zip(chunks, vectors, strict=True)):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                ordinal=i,
                text=chunk.text,
                embedding=vec,
                embedding_model=emb.name,
                embedding_version=emb.version,
                meta=chunk.meta,
            )
        )
    doc.index_status = IndexStatus.INDEXED
    bump(db, DataDomain.DOCUMENTS)


def needs_reindex(db: Session, doc_id: uuid.UUID) -> bool:
    """Fragmentos de antes de la indexación por frase (`sentence-v1`), o sin vectores."""
    rows = db.execute(
        select(DocumentChunk.meta["unit"].astext, DocumentChunk.embedding.is_(None)).where(
            DocumentChunk.document_id == doc_id
        )
    ).all()
    return not rows or any(unit != INDEX_UNIT or no_vector for unit, no_vector in rows)


def reindex(db: Session, emb: EmbeddingProvider, doc_id: uuid.UUID) -> DocumentOut:
    """Vuelve a fragmentar y vectorizar un documento desde el archivo guardado (mismo `id`, mismas citas)."""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise not_found("document_not_found", "No encontramos ese documento")
    data = (get_settings().storage_dir / doc.storage_path).read_bytes()
    chunks = to_sentences(parse(doc.filename, data))
    db.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    _index(db, emb, doc, chunks)
    db.commit()
    return _out(db, doc)


def delete(db: Session, doc_id: uuid.UUID) -> None:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise not_found("document_not_found", "No encontramos ese documento")
    path = get_settings().storage_dir / doc.storage_path
    db.delete(doc)
    bump(db, DataDomain.DOCUMENTS)
    db.commit()
    path.unlink(missing_ok=True)


def or_query(question: str) -> str | None:
    words = [w for w in re.findall(r"[a-z0-9]+", normalize(question)) if len(w) > 2]
    return " | ".join(dict.fromkeys(words)) or None


def has_documents(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(Document)) or 0) > 0


def search(db: Session, emb: EmbeddingProvider, question: str, k: int, min_similarity: float) -> list[Hit]:
    """Búsqueda híbrida. Devuelve como máximo `k` fragmentos relevantes (coincidencia de texto o similitud
    sobre el mínimo), ordenados por RRF."""
    ranks: dict[uuid.UUID, float] = {}
    chunks: dict[uuid.UUID, DocumentChunk] = {}
    sims: dict[uuid.UUID, float] = {}
    text_hits: set[uuid.UUID] = set()

    tsq = or_query(question)
    if tsq:
        query = func.to_tsquery(text("'spanish'"), tsq)
        rank = func.ts_rank(DocumentChunk.tsv, query)
        rows = db.execute(
            select(DocumentChunk, rank).where(DocumentChunk.tsv.op("@@")(query)).order_by(rank.desc()).limit(CANDIDATES)
        ).all()
        for pos, (chunk, _r) in enumerate(rows):
            chunks[chunk.id] = chunk
            text_hits.add(chunk.id)
            ranks[chunk.id] = ranks.get(chunk.id, 0) + 1 / (RRF_K + pos + 1)

    try:
        qv = emb.embed([question])[0]
        distance = DocumentChunk.embedding.cosine_distance(qv)
        rows = db.execute(
            select(DocumentChunk, distance)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(CANDIDATES)
        ).all()
        for pos, (chunk, dist) in enumerate(rows):
            chunks[chunk.id] = chunk
            sims[chunk.id] = 1 - float(dist)
            ranks[chunk.id] = ranks.get(chunk.id, 0) + 1 / (RRF_K + pos + 1)
    except EmbeddingsUnavailableError:
        pass

    relevant = [cid for cid in ranks if cid in text_hits or sims.get(cid, 0) >= min_similarity]
    relevant.sort(key=lambda cid: -ranks[cid])
    doc_ids = {chunks[c].document_id for c in relevant}
    docs = {d.id: d.filename for d in db.scalars(select(Document).where(Document.id.in_(doc_ids)))}
    return [
        Hit(
            chunk_id=cid,
            document_id=chunks[cid].document_id,
            filename=docs.get(chunks[cid].document_id, "documento"),
            text=chunks[cid].text,
            meta=chunks[cid].meta,
            score=round(ranks[cid], 5),
            similarity=round(sims[cid], 4) if cid in sims else None,
            text_match=cid in text_hits,
        )
        for cid in relevant[:k]
    ]

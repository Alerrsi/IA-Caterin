"""Fichas del negocio: sincronización incremental y búsqueda híbrida (ADR-006).

Todo pasa por la sesión de tenant: una pyme nunca ve ni sincroniza fichas de otra.
"""

import logging
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.embeddings import EmbeddingProvider, EmbeddingsUnavailableError
from app.db.enums import DataDomain
from app.db.models import DataVersion, KnowledgeCard, KnowledgeSync
from app.modules.documents.parsing import INDEX_UNIT
from app.modules.documents.service import CANDIDATES, RRF_K, Hit, or_query
from app.modules.knowledge.cards import BUILDERS, DEPENDS_ON, KINDS, SOURCE

logger = logging.getLogger(__name__)

EMBED_BATCH = 16
DOMAINS = tuple(sorted({d for deps in DEPENDS_ON.values() for d in deps}, key=lambda d: d.value))


def _versions(db: Session) -> dict[DataDomain, int]:
    rows = db.execute(
        select(DataVersion.domain, DataVersion.version).where(
            DataVersion.pyme_id == db.info["pyme_id"], DataVersion.domain.in_(DOMAINS)
        )
    ).all()
    return {d: v for d, v in rows}


def stale_kinds(db: Session) -> list[str]:
    current = _versions(db)
    synced = {s.domain: s.version for s in db.scalars(select(KnowledgeSync))}
    changed = {d for d in DOMAINS if current.get(d, 0) != synced.get(d)}
    return [k for k in KINDS if changed & set(DEPENDS_ON[k])]


def sync(db: Session, emb: EmbeddingProvider) -> int:
    """Pone al día las fichas de la pyme. Devuelve cuántas fichas se (re)vectorizaron.

    Solo regenera los tipos cuyos dominios cambiaron, y solo vectoriza las fichas cuyo texto cambió (o que
    quedaron sin vector porque los embeddings no estaban disponibles)."""
    kinds = stale_kinds(db)
    try:
        if kinds:
            versions = _versions(db)
            for kind in kinds:
                _rebuild(db, kind)
            for domain in DOMAINS:
                row = db.scalar(select(KnowledgeSync).where(KnowledgeSync.domain == domain))
                if row is None:
                    db.add(KnowledgeSync(domain=domain, version=versions.get(domain, 0)))
                else:
                    row.version = versions.get(domain, 0)
            db.flush()
        embedded = _embed_missing(db, emb)
        db.commit()
        return embedded
    except IntegrityError:  # otra consulta de la misma pyme sincronizó a la vez: sus fichas valen igual
        db.rollback()
        return 0


def _rebuild(db: Session, kind: str) -> None:
    fresh = {c.entity_id: c for c in BUILDERS[kind](db)}
    existing = {c.entity_id: c for c in db.scalars(select(KnowledgeCard).where(KnowledgeCard.kind == kind))}
    for entity_id, old in existing.items():
        if entity_id not in fresh:
            db.delete(old)  # entidad borrada o inactiva
    for entity_id, data in fresh.items():
        card = existing.get(entity_id)
        if card is None:
            db.add(
                KnowledgeCard(
                    kind=kind,
                    entity_id=entity_id,
                    title=data.title[:200],
                    text=data.text,
                    text_hash=data.text_hash,
                    embedding=None,
                    embedding_model="",
                    embedding_version="",
                )
            )
        elif card.text_hash != data.text_hash:
            card.title, card.text, card.text_hash, card.embedding = data.title[:200], data.text, data.text_hash, None


def _embed_missing(db: Session, emb: EmbeddingProvider) -> int:
    pending = list(
        db.scalars(
            select(KnowledgeCard).where(KnowledgeCard.embedding.is_(None) | (KnowledgeCard.embedding_model != emb.name))
        )
    )
    if not pending:
        return 0
    try:
        for start in range(0, len(pending), EMBED_BATCH):
            batch = pending[start : start + EMBED_BATCH]
            for card, vec in zip(batch, emb.embed([c.text for c in batch]), strict=True):
                card.embedding, card.embedding_model, card.embedding_version = vec, emb.name, emb.version
    except EmbeddingsUnavailableError:
        logger.warning("knowledge_embeddings_unavailable", extra={"pending": len(pending)})
        return 0
    return len(pending)


def has_cards(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(KnowledgeCard)) or 0) > 0


def cards_of(db: Session, kind: str) -> list[KnowledgeCard]:
    return list(db.scalars(select(KnowledgeCard).where(KnowledgeCard.kind == kind).order_by(KnowledgeCard.title)))


def _hit(card: KnowledgeCard, score: float, similarity: float | None, text_match: bool) -> Hit:
    label = f"{SOURCE[card.kind]}: {card.title}"
    return Hit(
        chunk_id=card.id,
        document_id=card.entity_id,
        filename=label,
        text=card.text,
        meta={"unit": INDEX_UNIT, "context": label, "card": card.kind},
        score=round(score, 5),
        similarity=round(similarity, 4) if similarity is not None else None,
        text_match=text_match,
    )


def search(db: Session, emb: EmbeddingProvider, question: str, k: int, min_similarity: float) -> list[Hit]:
    """Búsqueda híbrida sobre las fichas (texto completo sin tildes + pgvector, fusionados por RRF), igual que
    `documents.search`."""
    ranks: dict[uuid.UUID, float] = {}
    cards: dict[uuid.UUID, KnowledgeCard] = {}
    sims: dict[uuid.UUID, float] = {}
    text_hits: set[uuid.UUID] = set()
    tsq = or_query(question)
    if tsq:
        query = func.to_tsquery(text("'spanish'"), tsq)
        rank = func.ts_rank(KnowledgeCard.tsv, query)
        rows = db.execute(
            select(KnowledgeCard, rank).where(KnowledgeCard.tsv.op("@@")(query)).order_by(rank.desc()).limit(CANDIDATES)
        ).all()
        for pos, (card, _r) in enumerate(rows):
            cards[card.id] = card
            text_hits.add(card.id)
            ranks[card.id] = ranks.get(card.id, 0) + 1 / (RRF_K + pos + 1)
    try:
        qv = emb.embed([question])[0]
        distance = KnowledgeCard.embedding.cosine_distance(qv)
        rows = db.execute(
            select(KnowledgeCard, distance)
            .where(KnowledgeCard.embedding.is_not(None))
            .order_by(distance)
            .limit(CANDIDATES)
        ).all()
        for pos, (card, dist) in enumerate(rows):
            cards[card.id] = card
            sims[card.id] = 1 - float(dist)
            ranks[card.id] = ranks.get(card.id, 0) + 1 / (RRF_K + pos + 1)
    except EmbeddingsUnavailableError:
        pass
    relevant = [cid for cid in ranks if cid in text_hits or sims.get(cid, 0) >= min_similarity]
    relevant.sort(key=lambda cid: -ranks[cid])
    return [_hit(cards[c], ranks[c], sims.get(c), c in text_hits) for c in relevant[:k]]

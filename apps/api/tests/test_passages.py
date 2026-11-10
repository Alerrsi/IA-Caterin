"""Respuesta extractiva del nivel 2: indexación por frase y elección de la frase con su confianza (T10)."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.modules.assistant import passages
from app.modules.documents.parsing import CHUNK_CHARS, INDEX_UNIT, Chunk, embedding_text, split_text, to_sentences
from app.modules.documents.sentences import split_sentences

DOC = """# Condiciones — Harinas Cautín (SINTÉTICO)

## Despacho
Despachamos los martes y jueves sin costo. Para Labranza el despacho cuesta $6.000 y sale solo los jueves.

Sopaipillas: contienen gluten. No llevan huevo ni lácteos."""


@dataclass
class FakeHit:
    text: str
    meta: dict[str, Any]
    similarity: float | None
    filename: str = "condiciones-harinas-cautin.md"
    chunk_id: uuid.UUID = field(default_factory=uuid.uuid4)


def hits_for(similarities: dict[str, float]) -> list[FakeHit]:
    units = to_sentences(split_text(DOC, {}))
    return [FakeHit(u.text, u.meta, similarities.get(u.text, 0.3)) for u in units]


def test_sentences_carry_title_section_and_paragraph_label() -> None:
    by_text = {s.text: s for s in split_sentences(DOC)}
    labranza = by_text["Para Labranza el despacho cuesta $6.000 y sale solo los jueves."]
    assert labranza.context == "Condiciones — Harinas Cautín (SINTÉTICO) · Despacho"
    huevo = by_text["No llevan huevo ni lácteos."]
    assert huevo.context.endswith("Sopaipillas") and huevo.paragraph.startswith("Sopaipillas: contienen gluten.")
    assert "Despacho" not in by_text  # un encabezado corto da contexto, pero no es una respuesta


def test_table_rows_become_labeled_sentences() -> None:
    rows = split_sentences("producto | precio\nMantequilla | 2.490\nLeche | 1.090")
    assert [r.text for r in rows] == ["producto: Mantequilla; precio: 2.490", "producto: Leche; precio: 1.090"]


def test_pdf_lines_cut_in_half_are_joined() -> None:
    (s,) = split_sentences("Cada garzón ati\nende como máximo a 25 invitados.")
    assert s.text == "Cada garzón ati ende como máximo a 25 invitados."


def test_index_units_are_sentences_with_context_and_no_duplicates() -> None:
    units = to_sentences([Chunk(DOC, {"page": 1}), Chunk("Sopaipillas: contienen gluten. Otra frase.", {"page": 1})])
    texts = [u.text for u in units]
    assert len(texts) == len(set(texts)) and all(u.meta["unit"] == INDEX_UNIT and u.meta["page"] == 1 for u in units)
    huevo = next(u for u in units if u.text == "No llevan huevo ni lácteos.")
    assert huevo.meta["paragraph"].startswith("Sopaipillas:")
    assert embedding_text(huevo).startswith("Condiciones — Harinas Cautín (SINTÉTICO) · Despacho · Sopaipillas: ")


def test_long_paragraph_is_cut_at_a_sentence_end() -> None:
    text = " ".join(f"La frase número {i} termina aquí." for i in range(60))
    chunks = split_text(text, {})
    assert len(chunks) >= 2 and all(c.text.endswith(".") for c in chunks)
    assert all(len(c.text) <= CHUNK_CHARS for c in chunks) and chunks[1].text.startswith("La frase")


def test_best_passage_shows_the_sentence_that_answers_with_high_confidence() -> None:
    sentence = "Para Labranza el despacho cuesta $6.000 y sale solo los jueves."
    p = passages.best_passage("¿cuánto cobran por despachar a Labranza?", hits_for({sentence: 0.7}))
    assert p is not None and p.confidence == "high" and "$6.000" in p.text


def test_best_passage_shows_the_short_paragraph_so_the_subject_is_not_lost() -> None:
    p = passages.best_passage("¿las sopaipillas llevan huevo?", hits_for({"No llevan huevo ni lácteos.": 0.7}))
    assert p is not None and p.text.startswith("Sopaipillas: contienen gluten. No llevan huevo")


def test_absent_terms_lower_confidence_to_none() -> None:
    p = passages.best_passage("¿cuál es el RUT del notario de Pucón?", hits_for({}))
    assert p is not None and p.confidence == "none"


def test_confidence_thresholds() -> None:
    assert passages.confidence(0.7, 0.4) == "high"
    assert passages.confidence(0.8, 0.0) == "low"  # muy parecida, pero sin ningún término en común
    assert passages.confidence(0.5, 0.3) == "low"
    assert passages.confidence(0.4, 0.2) == "none"


def test_legacy_long_chunks_are_split_without_per_sentence_similarity() -> None:
    legacy = FakeHit(DOC, {}, 0.6)
    p = passages.best_passage("¿cuánto cobran por despachar a Labranza?", [legacy])
    assert p is not None and "$6.000" in p.text and p.similarity == 0.6  # hereda la del fragmento

"""Respuesta extractiva del nivel 2: qué frase responde la pregunta, y con cuánta seguridad (ADR-005, T10).

Determinista y sin LLM. Los documentos se indexan por frase (`documents.parsing.to_sentences`): la búsqueda
híbrida ya trae frases con su similitud de `bge-m3`. Cada candidata se puntúa con dos señales:

- **similitud** del vector de la frase (con su contexto) con la pregunta: capta paráfrasis ("¿cómo van
  vestidos los garzones?" ↔ "Uniforme: camisa blanca…");
- **cobertura**: qué parte de los términos de la pregunta aparece en la frase, ponderando cada término por lo
  raro que es entre las candidatas. Un término que no está en ninguna (como "RUT") pesa mucho y baja la
  cobertura: es la mejor pista de que la respuesta no está. El contexto (archivo, título, sección, etiqueta del
  párrafo) cuenta a la mitad.

La confianza decide qué se muestra (umbrales calibrados con `ml/evals/rag/calibrate_passages.py`):
- `high`: se responde con la frase (o su párrafo, si es corto), citada;
- `low`: se muestra lo más parecido, avisando que puede no ser la respuesta;
- `none`: se dice que no está en sus documentos (mejor que mostrar un fragmento que no corresponde).

Documentos indexados antes de `sentence-v1` (fragmentos de ~700 caracteres) se dividen en frases aquí y cada
frase hereda la similitud de su fragmento: funcionan, con menos precisión, hasta reindexarlos
(`python -m app.modules.documents.reindex`).
"""

import math
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.assistant.recognizer import normalize_question as normalize
from app.modules.documents.parsing import INDEX_UNIT
from app.modules.documents.sentences import split_sentences

Confidence = Literal["high", "low", "none"]

# Calibrados en T10 (10-nov-2026) con ml/evals/rag/calibrate_passages.py sobre el set de ajuste (questions.yaml,
# SINTÉTICO): la pregunta sin respuesta con mayor puntaje llegó a 0.66, y la confianza alta se fija en 0.72 para
# dejar margen en vez de pegarse al borde. La cobertura mínima de 0.2 para "alta" no cambia nada en ese set: es un
# resguardo para frases muy parecidas que no comparten ningún término con la pregunta. Ver ml/evals/REPORT.md.
SIMILARITY_WEIGHT = 1.0
COVERAGE_WEIGHT = 0.25
HIGH_MIN_SCORE = 0.72
HIGH_MIN_COVERAGE = 0.2
LOW_MIN_SCORE = 0.55
MAX_CHARS = 350
STEM = 5
CONTEXT_WEIGHT = 0.5

# Palabras que no dicen de qué trata la pregunta (texto ya normalizado: minúsculas y sin tildes).
_STOPWORDS = """
    a al algo algun alguna alguno ante aqui asi cada como con cual cuales cuando cuanto cuanta cuantos
    cuantas de del donde el ella ellos en entre era es esa ese eso esta estan este esto estos ha hace
    hacen hacer hay la las le les lo los me mi mis mucho muy nada ni no nos o oye para pero poco por porque
    puede pueden puedo pues que quien se sea ser si sobre son su sus tan te tiene tienen tengo toca
    todo todos tu tus un una uno unos unas usted va van y ya yo dime decir saber quiero necesito favor hola
"""
STOPWORDS = frozenset(_STOPWORDS.split())


@dataclass(frozen=True)
class Candidate:
    text: str
    context: str
    paragraph: str
    similarity: float | None
    hit_index: int


@dataclass(frozen=True)
class Passage:
    text: str
    hit_index: int
    coverage: float
    similarity: float | None
    score: float
    confidence: Confidence


def _stems(text: str) -> set[str]:
    return {w[:STEM] for w in normalize(text).split() if w not in STOPWORDS and (len(w) > 2 or w.isdigit())}


def candidates(hits: list[Any]) -> list[Candidate]:
    """Frases candidatas desde los resultados de `documents.search` (objetos con text, meta, filename y
    similarity)."""
    out: list[Candidate] = []
    for i, h in enumerate(hits):
        source = h.filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
        if h.meta.get("unit") == INDEX_UNIT:
            ctx = f"{source} {h.meta.get('context', '')}".strip()
            out.append(Candidate(h.text, ctx, h.meta.get("paragraph") or h.text, h.similarity, i))
        else:  # fragmento largo de antes de sentence-v1: todas sus frases heredan la similitud del fragmento
            out.extend(
                Candidate(s.text, f"{source} {s.context}".strip(), s.paragraph, h.similarity, i)
                for s in split_sentences(h.text)
            )
    return out


def coverages(question: str, cands: list[Candidate]) -> list[float]:
    terms = {t for t in _stems(question) if not t.isdigit()}
    numbers = {t for t in _stems(question) if t.isdigit()}
    own = [_stems(c.text) for c in cands]
    ctx = [_stems(c.context) for c in cands]
    n = len(cands)
    weights = {t: math.log(1 + n / (1 + sum(t in a or t in b for a, b in zip(own, ctx, strict=True)))) for t in terms}
    total = sum(weights.values())
    out = []
    for i in range(n):
        got = sum(w if t in own[i] else CONTEXT_WEIGHT * w if t in ctx[i] else 0.0 for t, w in weights.items())
        bonus = 0.1 * len(numbers & own[i])  # una cifra de la pregunta que está en la frase ayuda, sin decidir
        out.append(min(1.0, (got / total if total else 0.0) + bonus))
    return out


def score(similarity: float | None, coverage: float) -> float:
    return SIMILARITY_WEIGHT * (similarity or 0.0) + COVERAGE_WEIGHT * coverage


def confidence(similarity: float | None, coverage: float) -> Confidence:
    s = score(similarity, coverage)
    if s >= HIGH_MIN_SCORE and coverage >= HIGH_MIN_COVERAGE:
        return "high"
    return "low" if s >= LOW_MIN_SCORE else "none"


def best_passage(question: str, hits: list[Any]) -> Passage | None:
    """La frase que mejor responde, con sus señales y la confianza que se le puede tener. None sin frases."""
    cands = candidates(hits)
    if not cands:
        return None
    covs = coverages(question, cands)
    scores = [score(c.similarity, cv) for c, cv in zip(cands, covs, strict=True)]
    best = max(range(len(cands)), key=lambda i: (scores[i], -cands[i].hit_index, -i))  # empate: mejor rankeado
    chosen = cands[best]
    # El párrafo completo si es corto: "No llevan huevo ni lácteos." no se entiende sin "Sopaipillas: …".
    text = chosen.paragraph if len(chosen.paragraph) <= MAX_CHARS else chosen.text
    if len(text) > MAX_CHARS:
        cut = text.rfind(" ", 0, MAX_CHARS)
        text = text[: cut if cut > MAX_CHARS // 2 else MAX_CHARS] + "…"
    cov = round(covs[best], 3)
    return Passage(
        text, chosen.hit_index, cov, chosen.similarity, round(scores[best], 3), confidence(chosen.similarity, cov)
    )

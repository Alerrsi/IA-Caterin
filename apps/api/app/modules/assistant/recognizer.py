"""Reconocimiento de intención sin LLM: reglas y palabras clave, luego similitud con los ejemplos (ADR-005).

DESVIACIÓN del ADR: la similitud usa texto (rapidfuzz) y no embeddings `bge-m3`. Es más barato y no necesita
Ollama; se cambia por embeddings si la evaluación (T10) muestra que hace falta.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.modules.assistant.intents import Catalog, Intent

SIMILARITY_FLOOR = 0.40  # bajo esto una intención ni siquiera se ofrece como alternativa


def normalize_question(text: str) -> str:
    plain = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", plain))


@dataclass(frozen=True)
class Recognition:
    intent: str | None
    score: float
    margin: float
    via: str  # "keyword" | "similarity" | "none"
    alternatives: list[str] = field(default_factory=list)


def _similarity(question: str, intent: Intent) -> float:
    return max(fuzz.token_sort_ratio(question, normalize_question(e)) for e in intent.examples) / 100


def recognize(text: str, catalog: Catalog, threshold: float, min_margin: float) -> Recognition:
    q = normalize_question(text)
    sims = {i.name: _similarity(q, i) for i in catalog.intents}
    ranked = sorted(sims, key=lambda n: -sims[n])
    hits = [i.name for i in catalog.intents if any(re.search(p, q) for p in i.keywords)]
    if hits:  # una regla clara enruta directo; si coinciden varias, desempata la similitud
        best = max(hits, key=lambda n: sims[n])
        others = [sims[n] for n in hits if n != best]
        return Recognition(best, 1.0, round(sims[best] - max(others, default=0.0), 3), "keyword")
    best, second = ranked[0], sims[ranked[1]] if len(ranked) > 1 else 0.0
    margin = round(sims[best] - second, 3)
    alts = [n for n in ranked if sims[n] >= SIMILARITY_FLOOR][:3]
    if sims[best] >= threshold and margin >= min_margin:
        return Recognition(best, round(sims[best], 3), margin, "similarity", alts)
    return Recognition(None, round(sims[best], 3), margin, "none", alts)

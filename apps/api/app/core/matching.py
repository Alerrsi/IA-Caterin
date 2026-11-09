"""Resolución de nombres por coincidencia aproximada (rapidfuzz, MIT). ADR-005: el modelo no adivina.

Umbrales calibrados con las recetas del seed (T05; recalibrar en T10 con datos reales):
- se asocia solo si el mejor puntaje es >= 85 y supera al segundo por >= 10 puntos;
- si no, se ofrecen hasta 3 sugerencias con puntaje >= 60 para que la usuaria elija.
"""

import re
import unicodedata
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz, process

STOPWORDS = frozenset({"de", "del", "con", "la", "el", "los", "las", "y", "en", "al", "a", "un", "una", "unos", "unas"})
MATCH_MIN = 85.0
MATCH_MARGIN = 10.0
SUGGEST_MIN = 60.0


def normalize_name(text: str) -> str:
    plain = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return " ".join(w for w in re.findall(r"[a-z0-9]+", plain) if w not in STOPWORDS)


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    name: str
    score: float


@dataclass(frozen=True)
class MatchResult:
    match: Candidate | None
    suggestions: list[Candidate]


def match_name(query: str, choices: dict[uuid.UUID, str]) -> MatchResult:
    if not choices or not query.strip():
        return MatchResult(None, [])
    ids = list(choices)
    normalized = [normalize_name(choices[i]) for i in ids]
    ranked = process.extract(normalize_name(query), normalized, scorer=fuzz.token_set_ratio, limit=3)
    candidates = [Candidate(ids[idx], choices[ids[idx]], round(float(score), 1)) for _, score, idx in ranked]
    best = candidates[0]
    second = candidates[1].score if len(candidates) > 1 else 0.0
    if best.score >= MATCH_MIN and best.score - second >= MATCH_MARGIN:
        return MatchResult(best, [])
    return MatchResult(None, [c for c in candidates if c.score >= SUGGEST_MIN])

"""Resolución de entidades (insumos, recetas, proveedores) dentro de una pregunta libre, sin LLM. ADR-005."""

import uuid

from rapidfuzz import fuzz

from app.core.matching import (
    MATCH_MARGIN,
    MATCH_MIN,
    SUGGEST_MIN,
    Candidate,
    MatchResult,
    normalize_name,
)

MAX_NGRAM = 4
COVERAGE_GAP = 0.15  # cuánto más del nombre debe cubrir la pregunta para ganarle a otro nombre igual de parecido


def _score(grams: set[str], name: str) -> tuple[float, float]:
    """(parecido, cobertura). `token_set_ratio` da 100 a todo nombre que contenga las palabras dichas ("harina" ->
    "Harina sin polvos"); la cobertura mide qué parte del nombre completo mencionó la pregunta y desempata
    ("empanadas de queso" cubre más a "Empanadas de queso" que a "Empanadas de pino")."""
    norm = normalize_name(name)
    best = max(grams, key=lambda g: (fuzz.token_set_ratio(g, norm), fuzz.ratio(g, norm)))
    return fuzz.token_set_ratio(best, norm), fuzz.ratio(best, norm) / 100


def find_entity(text: str, choices: dict[uuid.UUID, str]) -> MatchResult:
    """Busca cuál nombre del catálogo menciona la pregunta (umbrales de `match_name`).

    Compara cada grupo de 1 a 4 palabras consecutivas de la pregunta con cada nombre. Si hay un ganador claro lo
    devuelve; si varios son igual de buenos, los ofrece como opciones (el asistente no adivina).
    """
    words = normalize_name(text).split()
    if not words or not choices:
        return MatchResult(None, [])
    grams = {" ".join(words[i : i + n]) for n in range(1, MAX_NGRAM + 1) for i in range(len(words) - n + 1)}
    # Si la pregunta trae el nombre completo, gana la coincidencia exacta más larga: "crema de leche" es
    # "Crema de leche" y no "Leche". Así las opciones que ofrece el asistente para aclarar siempre se resuelven.
    exact = [
        (i, name, len(normalize_name(name).split())) for i, name in choices.items() if normalize_name(name) in grams
    ]
    if exact:
        longest = max(n for _, _, n in exact)
        top = [(i, name) for i, name, n in exact if n == longest]
        if len(top) == 1:
            return MatchResult(Candidate(top[0][0], top[0][1], 100.0), [])
    scored = sorted(((i, name, *_score(grams, name)) for i, name in choices.items()), key=lambda r: (-r[2], -r[3]))[:3]
    cands = [Candidate(i, name, round(score, 1)) for i, name, score, _ in scored]
    (_, _, s1, c1), (s2, c2) = scored[0], (scored[1][2:] if len(scored) > 1 else (0.0, 0.0))
    if s1 >= MATCH_MIN and (s1 - s2 >= MATCH_MARGIN or c1 - c2 >= COVERAGE_GAP):
        return MatchResult(cands[0], [])
    return MatchResult(None, [c for c in cands if c.score >= SUGGEST_MIN])

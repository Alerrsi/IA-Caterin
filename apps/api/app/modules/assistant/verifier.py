"""Verificador de cifras (ADR-002): el LLM no puede agregar números que no estén en el dato que recibió."""

import re
from decimal import Decimal

from app.core.money import parse_cl_number
from app.modules.assistant.recognizer import normalize_question


def numbers(text: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for raw in re.findall(r"\d+(?:[.,]\d+)*", text):
        try:
            out.add(parse_cl_number(raw))
        except ValueError:
            continue
    return out


def figures_ok(answer: str, facts: str) -> bool:
    """True si todos los números del texto (formato chileno: $21.000, 2,5 kg) aparecen en los datos."""
    return numbers(answer) <= numbers(facts)


ECHO_IGNORED = frozenset(["el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "y", "o"])


def adds_content(answer: str, question: str) -> bool:
    """False si el texto no agrega ninguna palabra a la pregunta: el LLM la repitió ("con qué se hacen las brochetas
    de pollo" → lo mismo), visto con `qwen3:4b` en el nivel 2 (T10). Compara palabras enteras, no raíces: "Las
    sopaipillas no llevan huevo." sí agrega algo ("no") a "¿las sopaipillas llevan huevo?"."""
    return bool(set(normalize_question(answer).split()) - set(normalize_question(question).split()) - ECHO_IGNORED)


_NAME = re.compile(r"(?<![.!?¿¡«\"(:]\s)(?<!^)\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)")


def names_ok(answer: str, facts: str) -> bool:
    """True si cada nombre propio del texto (palabra con mayúscula que no inicia una frase) aparece en los datos.
    Atajó en T10 que `qwen3:4b` copiara el nombre del ejemplo del prompt ("Molino Sur") a una respuesta."""
    known = set(normalize_question(facts).split())
    return all(normalize_question(w) in known for w in _NAME.findall(answer.strip()))

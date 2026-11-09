"""Verificador de cifras (ADR-002): el LLM no puede agregar números que no estén en el dato que recibió."""

import re
from decimal import Decimal

from app.core.money import parse_cl_number


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

"""Fechas relativas en español de Chile, resueltas con reglas (nunca por el LLM). ADR-005."""

import re
import unicodedata
from datetime import date, timedelta

WEEKDAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def _safe(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _next_month_day(today: date, day: int) -> date | None:
    """El próximo día `day` (este mes si no ha pasado, si no el siguiente)."""
    candidate = _safe(today.year, today.month, day)
    if candidate and candidate >= today:
        return candidate
    month, year = (1, today.year + 1) if today.month == 12 else (today.month + 1, today.year)
    return _safe(year, month, day)


def parse_event_date(text: str | None, today: date) -> date | None:
    """Interpreta "mañana", "el sábado", "sábado 22", "22 de noviembre", "22/11", "2026-11-22"…

    Devuelve None si no hay una fecha clara (la usuaria la completa en la tabla editable).
    """
    if not text:
        return None
    t = _norm(text)

    if m := re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t):
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t):
        year = int(m[3]) if m[3] else today.year
        year = year + 2000 if year < 100 else year
        found = _safe(year, int(m[2]), int(m[1]))
        if found and not m[3] and found < today:
            found = _safe(year + 1, int(m[2]), int(m[1]))
        return found
    if m := re.search(r"\b(\d{1,2})\s+de\s+(" + "|".join(MONTHS) + r")\b", t):
        month = MONTHS[m[2]]
        found = _safe(today.year, month, int(m[1]))
        return _safe(today.year + 1, month, int(m[1])) if found and found < today else found
    if "pasado manana" in t:
        return today + timedelta(days=2)
    if re.search(r"\bmanana\b", t):
        return today + timedelta(days=1)
    if re.search(r"\bhoy\b", t):
        return today

    weekday = next((WEEKDAYS[w] for w in WEEKDAYS if re.search(rf"\b{w}\b", t)), None)
    day_num = re.search(r"\b(\d{1,2})\b", t)
    if weekday is not None and day_num:
        found = _next_month_day(today, int(day_num[1]))
        return found if found and found.weekday() == weekday else None  # "sábado 22" debe ser sábado
    if weekday is not None:
        delta = (weekday - today.weekday()) % 7
        return today + timedelta(days=delta or 7) if "proximo" in t or "otro" in t else today + timedelta(days=delta)
    if day_num and re.search(r"\b(el|dia)\s+\d{1,2}\b", t):
        return _next_month_day(today, int(day_num[1]))
    return None


_WD = "|".join(WEEKDAYS)
_MO = "|".join(MONTHS)
# Expresiones de fecha que parse_event_date entiende, en el mismo orden de prioridad.
_DATE_TEXT = [
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b(?!\s*(?:kg|kilos?|k|g|gr|grs|litros?|lt|l|docenas?)\b)"),
    re.compile(rf"\b(?:(?:{_WD})\s+)?\d{{1,2}}\s+de\s+(?:{_MO})\b"),
    re.compile(rf"\b(?:(?:el|este|esta|proximo|otro)\s+)?(?:{_WD})(?:\s+\d{{1,2}})?\b"),
    re.compile(r"\bpasado manana\b"),
    re.compile(r"\b(?:para|desde|el|hasta)\s+manana\b"),
    re.compile(r"\b(?:para|desde)\s+hoy\b"),
    re.compile(r"\b(?:el|dia)\s+\d{1,2}\b(?!\s*(?:docenas?|unidades?|kg|kilos?|personas?|invitados?)\b)"),
]


def find_date_text(text: str | None) -> str | None:
    """La expresión de fecha del mensaje, buscada por código (sin tildes y en minúsculas), o None.

    Sirve para no depender de que el LLM copie bien la fecha: si su texto no está en el mensaje, se usa este.
    """
    if not text:
        return None
    t = _norm(text)
    for rx in _DATE_TEXT:
        if m := rx.search(t):
            return m[0]
    return None


def appears_in(fragment: str, text: str) -> bool:
    """Si `fragment` está en `text`, sin contar tildes, mayúsculas ni espacios repetidos."""

    def squash(s: str) -> str:
        return re.sub(r"\s+", " ", _norm(s)).strip()

    return bool(squash(fragment)) and squash(fragment) in squash(text)

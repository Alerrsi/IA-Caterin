"""Cantidades y rangos de fechas en español de Chile, resueltos con reglas (nunca por el LLM). ADR-005."""

import re
from datetime import date, timedelta
from decimal import Decimal

from app.core.dates import _norm, parse_event_date

WEEKDAYS_SHORT = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
WEEKDAYS_LONG = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"
_NOT_QTY = (
    rf"(?!\s*(?:personas|invitados|pax|de (?:{_MONTHS})))"  # "para 50 personas" o "22 de noviembre" no son unidades
)
_DOZEN_WORDS = {"una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}


def fmt_date(d: date) -> str:
    return f"{WEEKDAYS_SHORT[d.weekday()]} {d.day}/{d.month}"


def parse_qty(text: str) -> Decimal | None:
    """ "una docena" -> 12, "media docena" -> 6, "2 docenas" -> 24, "50 canapés" -> 50. None si no hay cantidad clara.

    Heurística: un número suelto se toma como unidades salvo que hable de personas o de una fecha.
    """
    t = _norm(text)
    if re.search(r"\bmedia docena\b", t):
        return Decimal(6)
    if m := re.search(r"\b(\d+|" + "|".join(_DOZEN_WORDS) + r")\s+docenas?\b", t):
        n = int(m[1]) if m[1].isdigit() else _DOZEN_WORDS[m[1]]
        return Decimal(12 * n)
    if re.search(r"\bdocenas?\b", t):
        return Decimal(12)
    if m := re.search(r"\b(\d{1,5})\b" + _NOT_QTY, t):
        return Decimal(m[1]) if int(m[1]) > 0 else None
    return None


def parse_range(text: str, today: date) -> tuple[date, date, str]:
    """Rango de fechas pedido y su descripción. Sin indicación, los próximos 7 días."""
    t = _norm(text)
    sunday = today + timedelta(days=6 - today.weekday())
    if re.search(r"\b(proxima semana|semana que viene|siguiente semana)\b", t):
        start = sunday + timedelta(days=1)
        return start, start + timedelta(days=6), "la próxima semana"
    if re.search(r"\b(esta semana|la semana)\b", t):
        return today, sunday, "esta semana"
    if re.search(r"\bfin de semana\b", t):
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        return max(saturday, today), saturday + timedelta(days=1), "este fin de semana"
    if re.search(r"\b(este mes|el mes)\b", t):
        nxt = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
        return today, nxt - timedelta(days=1), "este mes"
    if m := re.search(r"\bproximos (\d{1,2}) dias\b", t):
        return today, today + timedelta(days=int(m[1])), f"los próximos {m[1]} días"
    if (one := parse_event_date(text, today)) is not None:
        label = {0: "hoy", 1: "mañana"}.get((one - today).days, fmt_date(one))
        return one, one, label
    return today, today + timedelta(days=7), "los próximos 7 días"

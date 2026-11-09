"""Dinero en CLP sin decimales (ADR-002). Nunca float."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CLP_STEP = Decimal("1")


def quantize_clp(value: Decimal) -> Decimal:
    return value.quantize(CLP_STEP, rounding=ROUND_HALF_UP)


def format_clp(value: Decimal) -> str:
    """$21.000 (formato chileno)."""
    q = quantize_clp(value)
    sign = "-" if q < 0 else ""
    return f"{sign}${int(abs(q)):,}".replace(",", ".")


def parse_cl_number(raw: str) -> Decimal:
    """Interpreta números escritos en Chile: "21.000" -> 21000, "2,5" -> 2.5, "$1.290" -> 1290, "1.234,5" -> 1234.5.

    Un punto seguido de exactamente 3 dígitos se toma como separador de miles ("21.000" es veintiún mil).
    """
    text = raw.strip().replace("$", "").replace(" ", "").replace(" ", "")
    if not text:
        raise ValueError("Número vacío")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") >= 1:
        parts = text.split(".")
        if all(len(p) == 3 for p in parts[1:]) and parts[0].lstrip("-").isdigit():
            text = "".join(parts)
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"No es un número: «{raw}»") from exc

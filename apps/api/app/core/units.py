"""Unidades y conversiones fijas (docs/DATA_MODEL.md, sección 5; ADR-002).

Todo se guarda en unidad base: g (masa), ml (volumen) o unit (contables).
Masa <-> volumen solo con una densidad explícita; nunca se asume.
"""

import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from app.db.enums import BaseUnit

QTY_STEP = Decimal("0.001")


class UnitConversionError(ValueError):
    """La unidad no existe o no se puede convertir a la unidad base del insumo."""


_UNITS: dict[str, tuple[BaseUnit, Decimal]] = {}


def _register(names: tuple[str, ...], base: BaseUnit, factor: str) -> None:
    for name in names:
        _UNITS[name] = (base, Decimal(factor))


_register(("g", "gr", "grs", "gramo", "gramos"), BaseUnit.GRAM, "1")
_register(("kg", "kgs", "kilo", "kilos", "kilogramo", "kilogramos"), BaseUnit.GRAM, "1000")
_register(("mg", "miligramo", "miligramos"), BaseUnit.GRAM, "0.001")
_register(("ml", "cc", "mililitro", "mililitros"), BaseUnit.MILLILITER, "1")
_register(("l", "lt", "lts", "litro", "litros"), BaseUnit.MILLILITER, "1000")
_register(("unit", "u", "un", "und", "uds", "unidad", "unidades"), BaseUnit.UNIT, "1")
_register(("dozen", "docena", "docenas"), BaseUnit.UNIT, "12")


def _normalize(raw: str) -> str:
    text = unicodedata.normalize("NFD", raw.strip().lower()).encode("ascii", "ignore").decode()
    return text.rstrip(".")


def parse_unit(raw: str) -> tuple[BaseUnit, Decimal]:
    """Devuelve (unidad base, factor) de una unidad escrita como "kg", "Kilos", "docena", "cc"…"""
    key = _normalize(raw)
    if key not in _UNITS:
        raise UnitConversionError(f"No conozco la unidad «{raw}»")
    return _UNITS[key]


def is_known_unit(raw: str) -> bool:
    return _normalize(raw) in _UNITS


def to_base(qty: Decimal, unit: str, base_unit: BaseUnit, density_g_per_ml: Decimal | None = None) -> Decimal:
    """Convierte `qty unit` a la unidad base del insumo."""
    kind, factor = parse_unit(unit)
    value = qty * factor
    if kind == base_unit:
        return value
    if {kind, base_unit} == {BaseUnit.GRAM, BaseUnit.MILLILITER}:
        if density_g_per_ml is None or density_g_per_ml <= 0:
            raise UnitConversionError("Para convertir entre peso y volumen hace falta la densidad del insumo")
        return value * density_g_per_ml if base_unit == BaseUnit.GRAM else value / density_g_per_ml
    raise UnitConversionError(f"No se puede convertir «{unit}» a {base_unit.value}")


def quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(QTY_STEP, rounding=ROUND_HALF_UP)


BASE_UNIT_LABELS: dict[BaseUnit, str] = {BaseUnit.GRAM: "g", BaseUnit.MILLILITER: "ml", BaseUnit.UNIT: "unidades"}


def human_qty(value: Decimal, base_unit: BaseUnit) -> str:
    """Formato legible en es-CL: 2500 g -> "2,5 kg"; 12 unidades -> "12 unidades"."""
    if base_unit == BaseUnit.GRAM and abs(value) >= 1000:
        return f"{format_decimal(value / 1000)} kg"
    if base_unit == BaseUnit.MILLILITER and abs(value) >= 1000:
        return f"{format_decimal(value / 1000)} L"
    return f"{format_decimal(value)} {BASE_UNIT_LABELS[base_unit]}"


def format_decimal(value: Decimal, max_decimals: int = 3) -> str:
    """Número con coma decimal y punto de miles (es-CL), sin ceros sobrantes."""
    q = value.quantize(Decimal(1).scaleb(-max_decimals), rounding=ROUND_HALF_UP).normalize()
    sign = "-" if q < 0 else ""
    integer, _, frac = f"{abs(q):f}".partition(".")
    integer = f"{int(integer):,}".replace(",", ".")
    return f"{sign}{integer},{frac}" if frac else f"{sign}{integer}"

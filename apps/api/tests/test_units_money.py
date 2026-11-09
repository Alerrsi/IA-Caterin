from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.money import format_clp, parse_cl_number, quantize_clp
from app.core.units import UnitConversionError, format_decimal, human_qty, parse_unit, to_base
from app.db.enums import BaseUnit


@pytest.mark.parametrize(
    ("qty", "unit", "base", "expected"),
    [
        ("2.5", "kg", BaseUnit.GRAM, "2500"),
        ("2.5", "Kilos", BaseUnit.GRAM, "2500"),
        ("300", "gr", BaseUnit.GRAM, "300"),
        ("1.5", "litros", BaseUnit.MILLILITER, "1500"),
        ("250", "cc", BaseUnit.MILLILITER, "250"),
        ("3", "docenas", BaseUnit.UNIT, "36"),
        ("7", "unidades", BaseUnit.UNIT, "7"),
        ("500", "mg", BaseUnit.GRAM, "0.5"),
    ],
)
def test_to_base(qty: str, unit: str, base: BaseUnit, expected: str) -> None:
    assert to_base(Decimal(qty), unit, base) == Decimal(expected)


def test_mass_volume_requires_density() -> None:
    with pytest.raises(UnitConversionError, match="densidad"):
        to_base(Decimal("1"), "l", BaseUnit.GRAM)
    assert to_base(Decimal("1"), "l", BaseUnit.GRAM, Decimal("0.92")) == Decimal("920.00")
    assert to_base(Decimal("920"), "g", BaseUnit.MILLILITER, Decimal("0.92")) == Decimal("1000")


def test_incompatible_and_unknown_units() -> None:
    with pytest.raises(UnitConversionError):
        to_base(Decimal("1"), "kg", BaseUnit.UNIT)
    with pytest.raises(UnitConversionError, match="taza"):
        parse_unit("taza")


def test_human_formats() -> None:
    assert human_qty(Decimal("2500"), BaseUnit.GRAM) == "2,5 kg"
    assert human_qty(Decimal("800"), BaseUnit.MILLILITER) == "800 ml"
    assert human_qty(Decimal("36"), BaseUnit.UNIT) == "36 unidades"
    assert format_decimal(Decimal("1234567.5")) == "1.234.567,5"
    assert format_clp(Decimal("21000")) == "$21.000"
    assert format_clp(Decimal("1290.5")) == "$1.291"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("21.000", "21000"), ("$1.290", "1290"), ("2,5", "2.5"), ("1.234,5", "1234.5"), ("2.5", "2.5"), ("15", "15")],
)
def test_parse_cl_number(raw: str, expected: str) -> None:
    assert parse_cl_number(raw) == Decimal(expected)


def test_parse_cl_number_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="número"):
        parse_cl_number("mucho")


@given(st.integers(min_value=0, max_value=10**10))
def test_clp_format_parse_roundtrip(value: int) -> None:
    assert parse_cl_number(format_clp(Decimal(value))) == Decimal(value)


@given(st.decimals(min_value=-(10**8), max_value=10**8, places=3, allow_nan=False))
def test_quantize_clp_has_no_decimals(value: Decimal) -> None:
    q = quantize_clp(value)
    assert q == q.to_integral_value()
    assert abs(q - value) <= Decimal("0.5")

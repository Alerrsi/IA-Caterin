import uuid
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.db.enums import BaseUnit
from app.modules.recipes.costing import (
    CostLineInput,
    PriceOption,
    best_option,
    effective_waste,
    recipe_cost,
    required_qty,
)

VAT = Decimal(19)


def opt(price: int, qty: str, supplier: str = "A", vat: bool = True, day: int = 1) -> PriceOption:
    return PriceOption(
        uuid.uuid4(), uuid.uuid4(), supplier, "x", Decimal(qty), Decimal(price), vat, date(2026, 11, day)
    )


def test_best_option_is_cheapest_per_base_unit() -> None:
    sack, bag = opt(21000, "25000"), opt(1290, "1000")
    assert best_option([bag, sack], VAT) is sack
    assert best_option([], VAT) is None


def test_net_prices_get_vat_before_comparing() -> None:
    net = opt(1000, "1000", vat=False)  # 1.190 con IVA
    gross = opt(1150, "1000")
    assert net.unit_price(VAT) == Decimal("1.19")
    assert best_option([net, gross], VAT) is gross


def test_tie_prefers_most_recent_price() -> None:
    old, new = opt(1000, "1000", "B", day=1), opt(1000, "1000", "A", day=5)
    assert best_option([old, new], VAT) is new


def test_required_qty_and_waste_priority() -> None:
    assert required_qty(Decimal(600), Decimal(12), Decimal(80), Decimal(5)) == Decimal("4200.000")
    assert effective_waste(Decimal(2), Decimal(10), Decimal(5)) == Decimal(2)
    assert effective_waste(None, Decimal(10), Decimal(5)) == Decimal(10)
    assert effective_waste(None, None, Decimal(5)) == Decimal(5)
    with pytest.raises(ValueError, match="rendimiento"):
        required_qty(Decimal(1), Decimal(0), Decimal(1), Decimal(0))


def test_recipe_cost_rounds_per_line_and_flags_missing_price() -> None:
    flour = CostLineInput(uuid.uuid4(), "Harina", BaseUnit.GRAM, Decimal(600), Decimal(5), [opt(21000, "25000")])
    dill = CostLineInput(uuid.uuid4(), "Eneldo", BaseUnit.GRAM, Decimal(5), Decimal(5), [])
    cost = recipe_cost([flour, dill], Decimal(12), Decimal(12), VAT)
    assert cost.lines[0].cost_clp == Decimal(529)  # 630 g × 0,84 = 529,2
    assert cost.lines[1].cost_clp is None
    assert cost.total_clp == Decimal(529)
    assert not cost.is_complete
    assert cost.per_unit_clp is None
    assert cost.missing_prices == ["Eneldo"]


@given(
    qty=st.decimals(min_value=1, max_value=5000, places=3),
    units=st.integers(min_value=1, max_value=2000),
    waste=st.decimals(min_value=0, max_value=50, places=2),
    price=st.integers(min_value=0, max_value=500000),
)
def test_cost_invariants(qty: Decimal, units: int, waste: Decimal, price: int) -> None:
    line = CostLineInput(uuid.uuid4(), "X", BaseUnit.GRAM, qty, waste, [opt(price, "1000")])
    small = recipe_cost([line], Decimal(12), Decimal(units), VAT)
    big = recipe_cost([line], Decimal(12), Decimal(units + 1), VAT)
    assert small.total_clp >= 0
    assert small.total_clp == small.total_clp.to_integral_value()
    assert big.total_clp >= small.total_clp  # producir más nunca cuesta menos

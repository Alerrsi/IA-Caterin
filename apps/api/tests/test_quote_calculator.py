"""Motor de cotización puro: casos de catering (unidades, mermas, redondeos, proveedor sin stock)."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.dates import find_date_text, parse_event_date
from app.core.matching import match_name
from app.db.enums import BaseUnit, OrderUnit
from app.modules.quotes.calculator import (
    IngredientInfo,
    ProductRequest,
    QuoteCalculationError,
    QuoteParams,
    RecipeInfo,
    RecipeLineInfo,
    calculate_quote,
    units_in_recipe_yield,
)
from app.modules.quotes.extractor import normalize_order_unit
from app.modules.recipes.costing import PriceOption

FLOUR, BEEF, DILL = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
PARAMS = QuoteParams(margin_pct=Decimal(40), vat_pct=Decimal(19), default_waste_pct=Decimal(5), use_stock=True)


def opt(price: int, qty: str, supplier: str = "Molino", label: str = "x") -> PriceOption:
    return PriceOption(
        uuid.uuid4(), uuid.uuid4(), supplier, label, Decimal(qty), Decimal(price), True, date(2026, 11, 2)
    )


def ingredients(flour_stock: str = "0", beef_stock: str = "0") -> dict[uuid.UUID, IngredientInfo]:
    return {
        FLOUR: IngredientInfo(FLOUR, "Harina", BaseUnit.GRAM, Decimal(flour_stock), None),
        BEEF: IngredientInfo(BEEF, "Carne", BaseUnit.GRAM, Decimal(beef_stock), None),
        DILL: IngredientInfo(DILL, "Eneldo", BaseUnit.GRAM, Decimal(0), None),
    }


EMPANADAS = RecipeInfo(
    uuid.uuid4(),
    "Empanadas",
    1,
    Decimal(12),
    BaseUnit.UNIT,
    [RecipeLineInfo(FLOUR, Decimal(600), None), RecipeLineInfo(BEEF, Decimal(700), None)],
)
CANAPES = RecipeInfo(uuid.uuid4(), "Canapés", 1, Decimal(24), BaseUnit.UNIT, [RecipeLineInfo(DILL, Decimal(5), None)])
SALAD = RecipeInfo(
    uuid.uuid4(), "Ensalada", 1, Decimal(1000), BaseUnit.GRAM, [RecipeLineInfo(BEEF, Decimal(100), None)]
)

OPTIONS = {
    FLOUR: [opt(21000, "25000", label="saco 25 kg"), opt(1290, "1000", label="bolsa 1 kg")],
    BEEF: [opt(7990, "1000", "Distribuidora", "1 kg")],
    DILL: [],
}


def test_units_conversion_to_recipe_yield() -> None:
    assert units_in_recipe_yield(Decimal(20), OrderUnit.DOZEN, EMPANADAS) == Decimal(240)
    assert units_in_recipe_yield(Decimal("2.5"), OrderUnit.KILOGRAM, SALAD) == Decimal(2500)
    with pytest.raises(QuoteCalculationError, match="porciones"):
        units_in_recipe_yield(Decimal(5), OrderUnit.PORTION, EMPANADAS)
    with pytest.raises(QuoteCalculationError, match="no se puede pedir en kg"):
        units_in_recipe_yield(Decimal(2), OrderUnit.KILOGRAM, EMPANADAS)


def test_hand_calculated_quote_without_stock() -> None:
    """12 empanadas sin stock. A mano:
    harina 600 g × 1,05 = 630 g; más barato por g: saco (0,84) -> costo 529,2 -> 529
    carne 700 g × 1,05 = 735 g × 7,99 = 5.872,65 -> 5.873 ; costo producto = 6.402
    precio unitario = 6.402 × 1,4 / 12 = 746,9 -> 747 ; subtotal = 747 × 12 = 8.964
    IVA = 8.964 × 0,19 = 1.703,16 -> 1.703 ; total = 10.667
    compra harina: 630 g -> 1 bolsa de 1 kg ($1.290) sale menos que 1 saco ($21.000)
    compra carne: 735 g -> 1 bolsa de 1 kg ($7.990)
    """
    req = ProductRequest(EMPANADAS, "empanadas de pino", Decimal(12), OrderUnit.UNIT)
    r = calculate_quote([req], ingredients(), OPTIONS, PARAMS)
    p = r.products[0]
    assert (p.cost_clp, p.unit_price_clp, p.subtotal_clp) == (Decimal(6402), Decimal(747), Decimal(8964))
    assert (r.net_clp, r.vat_clp, r.total_clp) == (Decimal(8964), Decimal(1703), Decimal(10667))
    by_name = {i.ingredient.name: i for i in r.ingredients}
    flour = by_name["Harina"]
    assert flour.required_qty == Decimal("630.000")
    assert flour.purchase is not None
    assert (flour.purchase.option.package_label, flour.purchase.packages) == ("bolsa 1 kg", 1)
    assert flour.purchase.total_clp == Decimal(1290)
    assert flour.alternatives[0].total_clp == Decimal(21000)
    assert r.shopping_total_clp == Decimal(1290 + 7990)
    assert r.is_complete


def test_stock_is_discounted_and_aggregated_across_products() -> None:
    reqs = [
        ProductRequest(EMPANADAS, "empanadas", Decimal(2), OrderUnit.DOZEN),
        ProductRequest(EMPANADAS, "más empanadas", Decimal(12), OrderUnit.UNIT),
    ]
    r = calculate_quote(reqs, ingredients(flour_stock="1000", beef_stock="-50"), OPTIONS, PARAMS)
    flour = next(i for i in r.ingredients if i.ingredient.name == "Harina")
    assert flour.required_qty == Decimal("1890.000")  # 630 × 3
    assert flour.stock_used_qty == Decimal("1000")
    assert flour.to_buy_qty == Decimal("890.000")
    beef = next(i for i in r.ingredients if i.ingredient.name == "Carne")
    assert beef.stock_used_qty == 0  # el stock negativo no se usa
    stocked = ingredients(flour_stock="5000", beef_stock="5000")
    covered = calculate_quote(reqs[:1], stocked, OPTIONS, PARAMS)
    assert all(i.purchase is None and i.note == "Cubierto con stock" for i in covered.ingredients)
    assert covered.shopping_total_clp == 0
    assert covered.total_clp > 0  # el stock también se cobra al cliente
    no_stock = calculate_quote(
        reqs[:1], ingredients(flour_stock="5000"), OPTIONS, PARAMS.__class__(**{**PARAMS.__dict__, "use_stock": False})
    )
    assert next(i for i in no_stock.ingredients if i.ingredient.name == "Harina").stock_used_qty == 0


def test_missing_price_makes_quote_incomplete() -> None:
    reqs = [ProductRequest(CANAPES, "canapés", Decimal(48), OrderUnit.UNIT)]
    r = calculate_quote(reqs, ingredients(), OPTIONS, PARAMS)
    assert not r.is_complete
    assert r.missing_prices == ["Eneldo"]
    assert r.products[0].unit_price_clp is None
    assert r.ingredients[0].note == "Sin proveedor con precio"
    with pytest.raises(QuoteCalculationError, match="no tiene productos"):
        calculate_quote([], ingredients(), OPTIONS, PARAMS)


@settings(max_examples=60, deadline=None)
@given(
    qty=st.integers(min_value=1, max_value=600),
    dozens=st.booleans(),
    margin=st.decimals(min_value=0, max_value=200, places=2),
    flour_stock=st.integers(min_value=0, max_value=50000),
)
def test_quote_invariants(qty: int, dozens: bool, margin: Decimal, flour_stock: int) -> None:
    params = QuoteParams(margin, Decimal(19), Decimal(5))
    unit = OrderUnit.DOZEN if dozens else OrderUnit.UNIT
    req = [ProductRequest(EMPANADAS, "e", Decimal(qty), unit)]
    r = calculate_quote(req, ingredients(flour_stock=str(flour_stock)), OPTIONS, params)
    p = r.products[0]
    assert p.unit_price_clp is not None and p.subtotal_clp is not None
    assert p.subtotal_clp == p.unit_price_clp * qty  # el PDF cuadra a la vista
    assert r.total_clp == r.net_clp + r.vat_clp
    assert all(v == v.to_integral_value() for v in (r.net_clp, r.vat_clp, r.total_clp, r.shopping_total_clp))
    assert r.net_clp >= r.ingredients_cost_clp - qty  # con margen >= 0 no se vende bajo costo (salvo redondeo)
    more_stock = calculate_quote(req, ingredients(flour_stock=str(flour_stock + 1000)), OPTIONS, params)
    assert more_stock.shopping_total_clp <= r.shopping_total_clp  # más stock nunca aumenta la compra


# --------------------------------------------------------------------------- fechas, nombres y unidades

TODAY = date(2026, 11, 9)  # lunes


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mañana", date(2026, 11, 10)),
        ("pasado mañana", date(2026, 11, 11)),
        ("el sábado", date(2026, 11, 14)),
        ("sábado 14", date(2026, 11, 14)),
        ("sábado 15", None),  # el 15 no es sábado: mejor preguntar
        ("el 22", date(2026, 11, 22)),
        ("el 3", date(2026, 12, 3)),
        ("22 de noviembre", date(2026, 11, 22)),
        ("5 de enero", date(2027, 1, 5)),
        ("22/11", date(2026, 11, 22)),
        ("22-11-2026", date(2026, 11, 22)),
        ("2026-12-24", date(2026, 12, 24)),
        ("31/02", None),
        ("cuando puedas", None),
        (None, None),
    ],
)
def test_parse_event_date(text: str | None, expected: date | None) -> None:
    assert parse_event_date(text, TODAY) == expected


def test_match_recipe_names() -> None:
    recipes = {uuid.uuid4(): n for n in ("Empanadas de pino", "Empanadas de queso", "Mini quiches", "Pie de limón")}
    by_name = {v: k for k, v in recipes.items()}
    assert match_name("empanaditas de pino", recipes).match.id == by_name["Empanadas de pino"]  # type: ignore[union-attr]
    ambiguous = match_name("empanadas", recipes)
    assert ambiguous.match is None
    assert {c.name for c in ambiguous.suggestions} == {"Empanadas de pino", "Empanadas de queso"}
    assert match_name("quiche", recipes).match is None  # 67: solo sugerencia
    assert match_name("tortas de mil hojas", recipes) == match_name("tortas de mil hojas", recipes)
    assert match_name("tortas de mil hojas", recipes).match is None


@pytest.mark.parametrize(
    ("raw", "unit", "warns"),
    [
        (None, OrderUnit.UNIT, False),
        ("docenas", OrderUnit.DOZEN, False),
        ("Kilos", OrderUnit.KILOGRAM, False),
        ("litro", OrderUnit.LITER, False),
        ("porciones", OrderUnit.PORTION, True),
        ("bandejas", OrderUnit.UNIT, True),
    ],
)
def test_normalize_order_unit(raw: str | None, unit: OrderUnit, warns: bool) -> None:
    got, warning = normalize_order_unit(raw)
    assert got == unit
    assert (warning is not None) == warns


def test_numbers_in_text_guard() -> None:
    from app.modules.quotes.extractor import numbers_in_text

    found = numbers_in_text("Necesito 200 brochetas, dos docenas de empanadas, 2,5 kilos y media docena. Total 1.000")
    assert {Decimal(200), Decimal(2), Decimal("2.5"), Decimal("0.5"), Decimal(1000)} <= found
    assert Decimal(201) not in found


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hola, para el sábado somos 40 personas, necesito 5 docenas de empanadas", date(2026, 11, 14)),
        ("80 empanadas para mañana en la mañana", date(2026, 11, 10)),
        ("el 22 de noviembre, 30 personas", date(2026, 11, 22)),
        ("evento el 21/11 a las 19 hrs", date(2026, 11, 21)),
        ("para el 5, 3 docenas de sopaipillas", date(2026, 12, 5)),
        ("1/2 kg de queso y 3 docenas de empanadas", None),  # medio kilo, no el 1 de febrero
        ("necesito el 5 docenas", None),
        ("quiero 3 docenas de sopaipillas", None),
    ],
)
def test_find_date_text_in_message(text: str, expected: date | None) -> None:
    """La fecha la encuentra el código en el mensaje, sin depender de que el LLM la copie bien."""
    assert parse_event_date(find_date_text(text), TODAY) == expected

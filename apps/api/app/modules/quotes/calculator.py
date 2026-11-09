"""Motor de cotización determinista (ADR-002). Funciones puras: sin base de datos ni LLM.

Pasos: pedido -> unidades por receta -> insumos necesarios (con merma) -> stock disponible ->
faltante -> presentaciones a comprar (la de menor total) -> costo de insumos -> precio al cliente.

Reglas de redondeo (CALC_VERSION; docs/DATA_MODEL.md, sección 5):
- Cantidades de insumo: 3 decimales, mitad hacia arriba, por receta y producto; luego se suman por insumo.
- Costo de un producto: suma por insumo de (necesario × precio por unidad base más barato), cada término
  redondeado a pesos (misma regla que el costo de receta, para que ambas pantallas cuadren).
- Precio unitario al cliente: costo × (1 + margen) / cantidad pedida, redondeado a pesos.
  El subtotal es precio unitario × cantidad (así el PDF cuadra a la vista).
- IVA: sobre el neto redondeado. Total = neto + IVA.
- Compra: presentaciones enteras (redondeo hacia arriba).
"""

import math
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.money import quantize_clp
from app.core.units import UnitConversionError, parse_unit, quantize_qty
from app.db.enums import BaseUnit, OrderUnit
from app.modules.recipes.costing import HUNDRED, PriceOption, best_option, effective_waste, required_qty

CALC_VERSION = "1.1.0"

ORDER_UNIT_LABELS = {
    OrderUnit.UNIT: ("unidad", "unidades"),
    OrderUnit.DOZEN: ("docena", "docenas"),
    OrderUnit.GRAM: ("g", "g"),
    OrderUnit.KILOGRAM: ("kg", "kg"),
    OrderUnit.MILLILITER: ("ml", "ml"),
    OrderUnit.LITER: ("L", "L"),
    OrderUnit.PORTION: ("porción", "porciones"),
}


class QuoteCalculationError(ValueError):
    """El pedido no se puede calcular tal como está (p. ej. unidad incompatible con la receta)."""


@dataclass(frozen=True)
class IngredientInfo:
    id: uuid.UUID
    name: str
    base_unit: BaseUnit
    stock_qty: Decimal
    waste_pct: Decimal | None


@dataclass(frozen=True)
class RecipeLineInfo:
    ingredient_id: uuid.UUID
    qty: Decimal  # por rendimiento, en unidad base del insumo
    waste_pct: Decimal | None


@dataclass(frozen=True)
class RecipeInfo:
    id: uuid.UUID
    name: str
    version: int
    yield_qty: Decimal
    yield_unit: BaseUnit
    lines: list[RecipeLineInfo]


@dataclass(frozen=True)
class ProductRequest:
    recipe: RecipeInfo
    requested_name: str
    qty: Decimal
    unit: OrderUnit


@dataclass(frozen=True)
class QuoteParams:
    margin_pct: Decimal
    vat_pct: Decimal
    default_waste_pct: Decimal
    use_stock: bool = True


@dataclass(frozen=True)
class PurchaseChoice:
    option: PriceOption
    packages: int
    total_clp: Decimal


@dataclass
class ProductResult:
    recipe_id: uuid.UUID
    recipe_name: str
    recipe_version: int
    requested_name: str
    qty: Decimal
    unit: OrderUnit
    units_in_yield: Decimal
    cost_clp: Decimal | None
    unit_price_clp: Decimal | None
    subtotal_clp: Decimal | None
    required: dict[uuid.UUID, Decimal] = field(default_factory=dict)

    @property
    def unit_label(self) -> str:
        singular, plural = ORDER_UNIT_LABELS[self.unit]
        return singular if self.qty == 1 else plural


@dataclass
class IngredientResult:
    ingredient: IngredientInfo
    required_qty: Decimal
    stock_used_qty: Decimal
    to_buy_qty: Decimal
    cheapest: PriceOption | None
    purchase: PurchaseChoice | None
    alternatives: list[PurchaseChoice]
    note: str | None


@dataclass
class QuoteResult:
    products: list[ProductResult]
    ingredients: list[IngredientResult]
    ingredients_cost_clp: Decimal
    net_clp: Decimal
    vat_clp: Decimal
    total_clp: Decimal
    shopping_total_clp: Decimal
    is_complete: bool
    missing_prices: list[str]
    params: QuoteParams
    calc_version: str = CALC_VERSION


def units_in_recipe_yield(qty: Decimal, unit: OrderUnit, recipe: RecipeInfo) -> Decimal:
    """Convierte la cantidad pedida a la unidad de rendimiento de la receta (p. ej. 20 docenas -> 240 unidades)."""
    if qty <= 0:
        raise QuoteCalculationError(f"La cantidad de «{recipe.name}» debe ser mayor que cero")
    if unit == OrderUnit.PORTION:
        raise QuoteCalculationError(
            f"«{recipe.name}» viene en porciones: indica cuántas unidades, docenas o kilos necesitas"
        )
    try:
        kind, factor = parse_unit(unit.value)
    except UnitConversionError as exc:  # pragma: no cover - todos los OrderUnit son conocidos
        raise QuoteCalculationError(str(exc)) from exc
    if kind != recipe.yield_unit:
        raise QuoteCalculationError(
            f"«{recipe.name}» rinde en {recipe.yield_unit.value}, no se puede pedir en {ORDER_UNIT_LABELS[unit][1]}"
        )
    return qty * factor


def choose_purchase(options: list[PriceOption], to_buy: Decimal, vat_pct: Decimal) -> list[PurchaseChoice]:
    """Todas las alternativas de compra ordenadas: menor total a pagar, luego menor precio unitario y más reciente."""
    choices = []
    for o in options:
        packages = math.ceil(to_buy / o.package_qty)
        choices.append(PurchaseChoice(o, packages, quantize_clp(o.gross_price(vat_pct) * packages)))
    return sorted(choices, key=lambda c: (c.total_clp, c.option.unit_price(vat_pct), -c.option.price_date.toordinal()))


def calculate_quote(
    products: list[ProductRequest],
    ingredients: dict[uuid.UUID, IngredientInfo],
    options: dict[uuid.UUID, list[PriceOption]],
    params: QuoteParams,
) -> QuoteResult:
    if not products:
        raise QuoteCalculationError("El pedido no tiene productos")
    vat = params.vat_pct
    cheapest = {ing_id: best_option(options.get(ing_id, []), vat) for ing_id in ingredients}

    product_results: list[ProductResult] = []
    totals: dict[uuid.UUID, Decimal] = {}
    for req in products:
        units = units_in_recipe_yield(req.qty, req.unit, req.recipe)
        required: dict[uuid.UUID, Decimal] = {}
        raw_cost = Decimal(0)
        complete = True
        for line in req.recipe.lines:
            ing = ingredients[line.ingredient_id]
            waste = effective_waste(line.waste_pct, ing.waste_pct, params.default_waste_pct)
            need = required_qty(line.qty, req.recipe.yield_qty, units, waste)
            required[ing.id] = required.get(ing.id, Decimal(0)) + need
            totals[ing.id] = totals.get(ing.id, Decimal(0)) + need
            option = cheapest[ing.id]
            if option is None:
                complete = False
            else:
                raw_cost += quantize_clp(need * option.unit_price(vat))
        cost = quantize_clp(raw_cost) if complete else None
        unit_price = quantize_clp(cost * (1 + params.margin_pct / HUNDRED) / req.qty) if cost is not None else None
        subtotal = quantize_clp(unit_price * req.qty) if unit_price is not None else None
        product_results.append(
            ProductResult(
                recipe_id=req.recipe.id,
                recipe_name=req.recipe.name,
                recipe_version=req.recipe.version,
                requested_name=req.requested_name,
                qty=req.qty,
                unit=req.unit,
                units_in_yield=units,
                cost_clp=cost,
                unit_price_clp=unit_price,
                subtotal_clp=subtotal,
                required=required,
            )
        )

    ingredient_results: list[IngredientResult] = []
    for ing_id, required_total in totals.items():
        ing = ingredients[ing_id]
        required_total = quantize_qty(required_total)
        available = max(ing.stock_qty, Decimal(0)) if params.use_stock else Decimal(0)
        stock_used = min(available, required_total)
        to_buy = required_total - stock_used
        choices = choose_purchase(options.get(ing_id, []), to_buy, vat) if to_buy > 0 else []
        if cheapest[ing_id] is None:
            note = "Sin proveedor con precio" if to_buy > 0 else "Cubierto con stock, pero sin precio para costear"
        elif to_buy == 0:
            note = "Cubierto con stock"
        else:
            note = None
        ingredient_results.append(
            IngredientResult(
                ingredient=ing,
                required_qty=required_total,
                stock_used_qty=stock_used,
                to_buy_qty=to_buy,
                cheapest=cheapest[ing_id],
                purchase=choices[0] if choices else None,
                alternatives=choices[1:],
                note=note,
            )
        )
    ingredient_results.sort(key=lambda r: r.ingredient.name.lower())

    missing = sorted({r.ingredient.name for r in ingredient_results if r.cheapest is None})
    complete = not missing
    ingredients_cost = sum((p.cost_clp for p in product_results if p.cost_clp is not None), Decimal(0))
    net = sum((p.subtotal_clp for p in product_results if p.subtotal_clp is not None), Decimal(0))
    vat_clp = quantize_clp(net * vat / HUNDRED)
    shopping = sum((r.purchase.total_clp for r in ingredient_results if r.purchase), Decimal(0))
    return QuoteResult(
        products=product_results,
        ingredients=ingredient_results,
        ingredients_cost_clp=ingredients_cost,
        net_clp=net,
        vat_clp=vat_clp,
        total_clp=net + vat_clp,
        shopping_total_clp=shopping,
        is_complete=complete,
        missing_prices=missing,
        params=params,
    )

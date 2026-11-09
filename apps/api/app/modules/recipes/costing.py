"""Costeo determinista de recetas (ADR-002). Funciones puras: sin base de datos ni LLM.

Supuestos (docs/tasks/T04):
- El costo usa, por insumo, la presentación vigente más barata por unidad base.
- Los costos se expresan CON IVA (lo que paga la pyme). Si un precio se ingresó sin IVA, se le suma.
- Insumo necesario = cantidad de la línea × (unidades pedidas / rendimiento) × (1 + merma %).
- Se redondea a pesos una vez por línea y después se suman las líneas.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.core.money import quantize_clp
from app.core.units import quantize_qty
from app.db.enums import BaseUnit

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class PriceOption:
    price_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    package_label: str
    package_qty: Decimal  # en unidad base
    price_clp: Decimal  # precio de la presentación tal como se ingresó
    includes_vat: bool
    price_date: date

    def gross_price(self, vat_pct: Decimal) -> Decimal:
        """Precio de la presentación con IVA, sin redondear."""
        return self.price_clp if self.includes_vat else self.price_clp * (1 + vat_pct / HUNDRED)

    def unit_price(self, vat_pct: Decimal) -> Decimal:
        """Precio con IVA por unidad base (g, ml o unidad), con precisión completa."""
        return self.gross_price(vat_pct) / self.package_qty


def best_option(options: list[PriceOption], vat_pct: Decimal) -> PriceOption | None:
    """La más barata por unidad base; en empate, la de precio más reciente y luego por nombre de proveedor."""
    if not options:
        return None
    return min(options, key=lambda o: (o.unit_price(vat_pct), -o.price_date.toordinal(), o.supplier_name))


def effective_waste(line_waste: Decimal | None, ingredient_waste: Decimal | None, pyme_waste: Decimal) -> Decimal:
    for value in (line_waste, ingredient_waste):
        if value is not None:
            return value
    return pyme_waste


def required_qty(qty_per_yield: Decimal, yield_qty: Decimal, units: Decimal, waste_pct: Decimal) -> Decimal:
    """Cantidad de insumo (unidad base) para producir `units` unidades de una receta, con merma."""
    if yield_qty <= 0:
        raise ValueError("El rendimiento de la receta debe ser mayor que cero")
    return quantize_qty(qty_per_yield * units / yield_qty * (1 + waste_pct / HUNDRED))


@dataclass(frozen=True)
class CostLineInput:
    ingredient_id: uuid.UUID
    ingredient_name: str
    base_unit: BaseUnit
    qty_per_yield: Decimal
    waste_pct: Decimal
    options: list[PriceOption] = field(default_factory=list)


@dataclass(frozen=True)
class CostLine:
    ingredient_id: uuid.UUID
    ingredient_name: str
    base_unit: BaseUnit
    required_qty: Decimal
    waste_pct: Decimal
    price: PriceOption | None
    unit_price_clp: Decimal | None  # por unidad base, con IVA, sin redondear
    cost_clp: Decimal | None  # redondeado a pesos


@dataclass(frozen=True)
class RecipeCost:
    units: Decimal
    lines: list[CostLine]
    total_clp: Decimal
    per_unit_clp: Decimal | None
    is_complete: bool  # False si a alguna línea le falta precio: el total es parcial

    @property
    def missing_prices(self) -> list[str]:
        return [line.ingredient_name for line in self.lines if line.price is None]


def recipe_cost(lines: list[CostLineInput], yield_qty: Decimal, units: Decimal, vat_pct: Decimal) -> RecipeCost:
    if units <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    out: list[CostLine] = []
    for line in lines:
        needed = required_qty(line.qty_per_yield, yield_qty, units, line.waste_pct)
        option = best_option(line.options, vat_pct)
        unit_price = option.unit_price(vat_pct) if option else None
        cost = quantize_clp(needed * unit_price) if unit_price is not None else None
        out.append(
            CostLine(
                line.ingredient_id,
                line.ingredient_name,
                line.base_unit,
                needed,
                line.waste_pct,
                option,
                unit_price,
                cost,
            )
        )
    total = sum((line.cost_clp for line in out if line.cost_clp is not None), Decimal(0))
    complete = all(line.price is not None for line in out)
    return RecipeCost(units, out, total, quantize_clp(total / units) if complete else None, complete)

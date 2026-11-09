"""Proveedores y precios versionados: un precio no se edita, se crea una versión nueva."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.money import quantize_clp
from app.core.units import quantize_qty
from app.db.enums import BaseUnit, DataDomain, PriceSourceKind
from app.db.models import Ingredient, IngredientPrice, Pyme, Supplier
from app.modules.inventory.service import convert_qty, get_ingredient
from app.modules.recipes.costing import PriceOption, best_option
from app.modules.suppliers.schemas import (
    PriceComparison,
    PriceComparisonItem,
    PriceCreate,
    SupplierCreate,
    SupplierUpdate,
)

_DUPLICATE = ProblemError(409, "supplier_exists", "Ya tienes un proveedor con ese nombre")
REFERENCE = {
    BaseUnit.GRAM: ("kg", Decimal(1000)),
    BaseUnit.MILLILITER: ("L", Decimal(1000)),
    BaseUnit.UNIT: ("unidad", Decimal(1)),
}


def list_suppliers(db: Session, include_inactive: bool = False) -> list[Supplier]:
    stmt = select(Supplier).order_by(func.lower(Supplier.name))
    if not include_inactive:
        stmt = stmt.where(Supplier.is_active)
    return list(db.scalars(stmt))


def get_supplier(db: Session, supplier_id: uuid.UUID) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise not_found("supplier_not_found", "No encontramos ese proveedor")
    return supplier


def find_supplier_by_name(db: Session, name: str) -> Supplier | None:
    return db.scalar(select(Supplier).where(func.lower(Supplier.name) == " ".join(name.split()).lower()))


def create_supplier(db: Session, data: SupplierCreate, commit: bool = True) -> Supplier:
    supplier = Supplier(**data.model_dump())
    supplier.name = " ".join(supplier.name.split())
    db.add(supplier)
    try:
        db.flush()
        bump(db, DataDomain.SUPPLIERS)
        if commit:
            db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _DUPLICATE from exc
    return supplier


def update_supplier(db: Session, supplier_id: uuid.UUID, data: SupplierUpdate) -> Supplier:
    supplier = get_supplier(db, supplier_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in ("name", "is_active") and value is None:
            continue
        setattr(supplier, field, " ".join(value.split()) if field == "name" else value)
    try:
        bump(db, DataDomain.SUPPLIERS)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _DUPLICATE from exc
    db.refresh(supplier)
    return supplier


def create_price(
    db: Session,
    data: PriceCreate,
    source: PriceSourceKind = PriceSourceKind.MANUAL,
    import_batch_id: uuid.UUID | None = None,
    commit: bool = True,
) -> IngredientPrice:
    """Crea una versión nueva del precio; la anterior de la misma presentación deja de estar vigente."""
    ing = get_ingredient(db, data.ingredient_id)
    get_supplier(db, data.supplier_id)
    package_qty = quantize_qty(convert_qty(data.package_qty, data.package_unit, ing))
    if package_qty <= 0:
        raise ProblemError(422, "invalid_package", "La cantidad de la presentación debe ser mayor que cero")
    label = " ".join(data.package_label.split())
    db.execute(
        update(IngredientPrice)
        .where(
            IngredientPrice.ingredient_id == ing.id,
            IngredientPrice.supplier_id == data.supplier_id,
            IngredientPrice.package_label == label,
            IngredientPrice.is_current,
        )
        .values(is_current=False)
    )
    price = IngredientPrice(
        ingredient_id=ing.id,
        supplier_id=data.supplier_id,
        package_label=label,
        package_qty=package_qty,
        price_clp=Decimal(data.price_clp),
        includes_vat=data.includes_vat,
        price_date=data.price_date,
        source=source,
        import_batch_id=import_batch_id,
        is_current=True,
    )
    db.add(price)
    db.flush()
    bump(db, DataDomain.SUPPLIERS, DataDomain.RECIPES)
    if commit:
        db.commit()
    return price


def list_prices(
    db: Session, ingredient_id: uuid.UUID | None, supplier_id: uuid.UUID | None, include_history: bool = False
) -> list[IngredientPrice]:
    stmt = select(IngredientPrice).order_by(IngredientPrice.price_date.desc(), IngredientPrice.created_at.desc())
    if ingredient_id:
        stmt = stmt.where(IngredientPrice.ingredient_id == ingredient_id)
    if supplier_id:
        stmt = stmt.where(IngredientPrice.supplier_id == supplier_id)
    if not include_history:
        stmt = stmt.where(IngredientPrice.is_current)
    return list(db.scalars(stmt))


def current_options(db: Session, ingredient_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[PriceOption]]:
    """Ofertas vigentes de proveedores activos para varios insumos (una sola consulta)."""
    if not ingredient_ids:
        return {}
    stmt = (
        select(IngredientPrice)
        .join(Supplier, (Supplier.id == IngredientPrice.supplier_id) & (Supplier.pyme_id == IngredientPrice.pyme_id))
        .where(IngredientPrice.ingredient_id.in_(ingredient_ids), IngredientPrice.is_current, Supplier.is_active)
        .options(selectinload(IngredientPrice.supplier))
    )
    out: dict[uuid.UUID, list[PriceOption]] = {i: [] for i in ingredient_ids}
    for p in db.scalars(stmt):
        out[p.ingredient_id].append(
            PriceOption(
                price_id=p.id,
                supplier_id=p.supplier_id,
                supplier_name=p.supplier.name,
                package_label=p.package_label,
                package_qty=p.package_qty,
                price_clp=p.price_clp,
                includes_vat=p.includes_vat,
                price_date=p.price_date,
            )
        )
    return out


def vat_pct(db: Session) -> Decimal:
    pyme = db.get(Pyme, db.info["pyme_id"])
    return pyme.vat_pct if pyme else Decimal("19")


def compare_prices(db: Session, ingredient_id: uuid.UUID) -> PriceComparison:
    ing: Ingredient = get_ingredient(db, ingredient_id)
    vat = vat_pct(db)
    options = current_options(db, [ing.id])[ing.id]
    best = best_option(options, vat)
    ref_label, ref_factor = REFERENCE[ing.base_unit]
    items = [
        PriceComparisonItem(
            price_id=o.price_id,
            supplier_id=o.supplier_id,
            supplier_name=o.supplier_name,
            package_label=o.package_label,
            package_qty=o.package_qty,
            price_clp=int(o.price_clp),
            includes_vat=o.includes_vat,
            price_date=o.price_date,
            gross_price_clp=int(quantize_clp(o.gross_price(vat))),
            price_per_base_unit_clp=o.unit_price(vat).quantize(Decimal("0.0001")),
            price_per_reference_clp=int(quantize_clp(o.unit_price(vat) * ref_factor)),
            reference_unit=ref_label,
            is_best=best is not None and o.price_id == best.price_id,
        )
        for o in sorted(options, key=lambda o: o.unit_price(vat))
    ]
    return PriceComparison(ingredient_id=ing.id, ingredient_name=ing.name, base_unit=ing.base_unit, items=items)

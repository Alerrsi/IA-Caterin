"""Importación de insumos y precios desde CSV/Excel.

Flujo sin estado en el servidor:
1. `preview`: se lee el archivo y se devuelven las filas válidas (ya normalizadas) y los errores por fila.
2. `confirm`: el cliente reenvía las filas válidas; se validan de nuevo y se guardan con un `import_batch_id`.
3. `undo`: se deshace una importación si sus datos no se han usado.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.core.data_version import bump
from app.core.errors import ProblemError, not_found
from app.core.money import parse_cl_number
from app.core.units import UnitConversionError, parse_unit, quantize_qty
from app.db.enums import BaseUnit, DataDomain, MovementReason, PriceSourceKind
from app.db.models import Ingredient, IngredientPrice, QuoteLine, RecipeLine, StockMovement
from app.modules.imports.parsing import pick, read_table
from app.modules.inventory.schemas import IngredientCreate
from app.modules.inventory.service import create_ingredient
from app.modules.suppliers.schemas import PriceCreate, SupplierCreate
from app.modules.suppliers.service import create_price, create_supplier, find_supplier_by_name

INGREDIENT_TEMPLATE = (
    "nombre;unidad;stock;stock_minimo;merma_pct;categoria\n"
    "Harina sin polvos;kg;18;5;;Abarrotes\n"
    "Huevo;unidad;90;30;;Lácteos y huevos\n"
)
PRICE_TEMPLATE = (
    "insumo;proveedor;presentacion;cantidad;unidad;precio;incluye_iva;fecha\n"
    "Harina sin polvos;Molino de ejemplo;saco 25 kg;25;kg;21.000;si;02-11-2026\n"
)

YES = {"si", "sí", "s", "true", "1", "x", "yes"}
NO = {"no", "n", "false", "0"}


class RowIssue(BaseModel):
    row: int = Field(description="Número de fila en la planilla (la 1 es el encabezado)")
    field: str
    message: str


class IngredientRow(BaseModel):
    row: int
    name: str = Field(min_length=2, max_length=120)
    base_unit: BaseUnit
    stock_qty: Decimal = Field(ge=0)
    min_stock_qty: Decimal | None = Field(default=None, ge=0)
    waste_pct: Decimal | None = Field(default=None, ge=0, lt=100)
    category: str | None = Field(default=None, max_length=60)


class PriceRow(BaseModel):
    row: int
    ingredient_id: uuid.UUID
    ingredient_name: str
    supplier_name: str = Field(min_length=2, max_length=120)
    supplier_is_new: bool
    package_label: str = Field(min_length=1, max_length=80)
    package_qty: Decimal = Field(gt=0, description="En unidad base del insumo")
    price_clp: int = Field(ge=0)
    includes_vat: bool
    price_date: date


class IngredientPreview(BaseModel):
    total_rows: int
    valid: list[IngredientRow]
    errors: list[RowIssue]


class PricePreview(BaseModel):
    total_rows: int
    valid: list[PriceRow]
    errors: list[RowIssue]
    source: PriceSourceKind


class IngredientConfirm(BaseModel):
    rows: list[IngredientRow] = Field(min_length=1, max_length=2000)


class PriceConfirm(BaseModel):
    rows: list[PriceRow] = Field(min_length=1, max_length=2000)
    source: PriceSourceKind = PriceSourceKind.CSV


class ImportResult(BaseModel):
    import_batch_id: uuid.UUID
    created: int
    suppliers_created: int = 0


class UndoResult(BaseModel):
    ingredients_deleted: int
    prices_deleted: int


def _number(raw: str, field: str, row: int, issues: list[RowIssue], required: bool = False) -> Decimal | None:
    if not raw:
        if required:
            issues.append(RowIssue(row=row, field=field, message="Falta este dato"))
        return None
    try:
        value = parse_cl_number(raw)
    except ValueError:
        issues.append(RowIssue(row=row, field=field, message=f"«{raw}» no es un número"))
        return None
    if value < 0:
        issues.append(RowIssue(row=row, field=field, message="No puede ser negativo"))
        return None
    return value


def _date(raw: str, row: int, issues: list[RowIssue]) -> date | None:
    if not raw:
        return date.today()  # noqa: DTZ011 - fecha local; se informa en la vista previa
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw.split(" ")[0], fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    issues.append(RowIssue(row=row, field="fecha", message=f"«{raw}» no es una fecha (usa dd-mm-aaaa)"))
    return None


def _existing_names(db: Session) -> dict[str, Ingredient]:
    return {i.name.lower(): i for i in db.scalars(select(Ingredient))}


# --------------------------------------------------------------------------- insumos


def preview_ingredients(db: Session, filename: str, data: bytes) -> IngredientPreview:
    table = read_table(filename, data)
    existing = _existing_names(db)
    seen: set[str] = set()
    valid: list[IngredientRow] = []
    errors: list[RowIssue] = []
    for idx, raw in enumerate(table):
        row = idx + 2
        issues: list[RowIssue] = []
        name = " ".join(pick(raw, "nombre", "insumo", "producto").split())
        if len(name) < 2:
            issues.append(RowIssue(row=row, field="nombre", message="Falta el nombre"))
        elif name.lower() in existing:
            issues.append(RowIssue(row=row, field="nombre", message="Ya tienes un insumo con ese nombre"))
        elif name.lower() in seen:
            issues.append(RowIssue(row=row, field="nombre", message="Está repetido en la planilla"))
        unit_raw = pick(raw, "unidad", "unidad_de_medida", "um")
        base: BaseUnit | None = None
        factor = Decimal(1)
        try:
            base, factor = parse_unit(unit_raw or "")
        except UnitConversionError:
            issues.append(
                RowIssue(
                    row=row, field="unidad", message=f"No conozco la unidad «{unit_raw}» (usa kg, g, l, ml o unidad)"
                )
            )
        stock = _number(pick(raw, "stock", "cantidad", "stock_actual"), "stock", row, issues)
        minimum = _number(pick(raw, "stock_minimo", "minimo"), "stock_minimo", row, issues)
        waste = _number(pick(raw, "merma_pct", "merma"), "merma_pct", row, issues)
        if waste is not None and waste >= 100:
            issues.append(RowIssue(row=row, field="merma_pct", message="La merma debe ser menor que 100"))
        if issues or base is None:
            errors.extend(issues)
            continue
        seen.add(name.lower())
        valid.append(
            IngredientRow(
                row=row,
                name=name,
                base_unit=base,
                stock_qty=quantize_qty((stock or Decimal(0)) * factor),
                min_stock_qty=quantize_qty(minimum * factor) if minimum is not None else None,
                waste_pct=waste,
                category=pick(raw, "categoria", "familia") or None,
            )
        )
    return IngredientPreview(total_rows=len(table), valid=valid, errors=errors)


def confirm_ingredients(db: Session, data: IngredientConfirm) -> ImportResult:
    existing = _existing_names(db)
    names = [r.name.lower() for r in data.rows]
    clashes = sorted({n for n in names if n in existing} | {n for n in names if names.count(n) > 1})
    if clashes:
        raise ProblemError(409, "import_conflict", "Algunos insumos ya existen o están repetidos", ", ".join(clashes))
    batch = uuid.uuid4()
    for r in data.rows:
        create_ingredient(
            db,
            IngredientCreate(
                name=r.name,
                base_unit=r.base_unit,
                initial_stock=r.stock_qty,
                min_stock_qty=r.min_stock_qty,
                waste_pct=r.waste_pct,
                category=r.category,
            ),
            import_batch_id=batch,
        )
    db.commit()
    return ImportResult(import_batch_id=batch, created=len(data.rows))


# --------------------------------------------------------------------------- precios


def preview_prices(db: Session, filename: str, data: bytes) -> PricePreview:
    source = PriceSourceKind.EXCEL if data.startswith(b"PK\x03\x04") else PriceSourceKind.CSV
    table = read_table(filename, data)
    ingredients = _existing_names(db)
    valid: list[PriceRow] = []
    errors: list[RowIssue] = []
    for idx, raw in enumerate(table):
        row = idx + 2
        issues: list[RowIssue] = []
        ing_name = " ".join(pick(raw, "insumo", "nombre", "producto").split())
        ing = ingredients.get(ing_name.lower())
        if ing is None:
            issues.append(
                RowIssue(row=row, field="insumo", message=f"No existe el insumo «{ing_name}»; créalo primero")
            )
        supplier = " ".join(pick(raw, "proveedor").split())
        if len(supplier) < 2:
            issues.append(RowIssue(row=row, field="proveedor", message="Falta el proveedor"))
        qty = _number(pick(raw, "cantidad", "contenido"), "cantidad", row, issues, required=True)
        unit_raw = pick(raw, "unidad", "um")
        price = _number(pick(raw, "precio", "precio_clp", "valor"), "precio", row, issues, required=True)
        vat_raw = pick(raw, "incluye_iva", "con_iva", "iva").lower()
        if vat_raw and vat_raw not in YES | NO:
            issues.append(RowIssue(row=row, field="incluye_iva", message="Escribe «si» o «no»"))
        price_date = _date(pick(raw, "fecha", "fecha_precio"), row, issues)
        package_qty: Decimal | None = None
        if ing is not None and qty is not None:
            try:
                kind, factor = parse_unit(unit_raw) if unit_raw else (ing.base_unit, Decimal(1))
                if kind != ing.base_unit:
                    raise UnitConversionError(f"«{unit_raw}» no sirve para {ing.name} ({ing.base_unit.value})")
                package_qty = quantize_qty(qty * factor)
                if package_qty <= 0:
                    issues.append(RowIssue(row=row, field="cantidad", message="Debe ser mayor que cero"))
            except UnitConversionError as exc:
                issues.append(RowIssue(row=row, field="unidad", message=str(exc)))
        if price is not None and price != price.to_integral_value():
            issues.append(RowIssue(row=row, field="precio", message="El precio va en pesos, sin decimales"))
        if issues or ing is None or package_qty is None or price is None or price_date is None:
            errors.extend(issues)
            continue
        label = " ".join(pick(raw, "presentacion", "formato").split()) or f"{qty} {unit_raw or ing.base_unit.value}"
        valid.append(
            PriceRow(
                row=row,
                ingredient_id=ing.id,
                ingredient_name=ing.name,
                supplier_name=supplier,
                supplier_is_new=find_supplier_by_name(db, supplier) is None,
                package_label=label,
                package_qty=package_qty,
                price_clp=int(price),
                includes_vat=vat_raw not in NO,
                price_date=price_date,
            )
        )
    return PricePreview(total_rows=len(table), valid=valid, errors=errors, source=source)


def confirm_prices(db: Session, data: PriceConfirm) -> ImportResult:
    batch = uuid.uuid4()
    suppliers_created = 0
    for r in data.rows:
        supplier = find_supplier_by_name(db, r.supplier_name)
        if supplier is None:
            supplier = create_supplier(db, SupplierCreate(name=r.supplier_name), commit=False)
            suppliers_created += 1
        create_price(
            db,
            PriceCreate(
                ingredient_id=r.ingredient_id,
                supplier_id=supplier.id,
                package_label=r.package_label,
                package_qty=r.package_qty,
                price_clp=r.price_clp,
                includes_vat=r.includes_vat,
                price_date=r.price_date,
            ),
            source=data.source,
            import_batch_id=batch,
            commit=False,
        )
    db.commit()
    return ImportResult(import_batch_id=batch, created=len(data.rows), suppliers_created=suppliers_created)


# --------------------------------------------------------------------------- deshacer


def undo_import(db: Session, batch_id: uuid.UUID) -> UndoResult:
    prices = list(db.scalars(select(IngredientPrice).where(IngredientPrice.import_batch_id == batch_id)))
    ingredients = list(db.scalars(select(Ingredient).where(Ingredient.import_batch_id == batch_id)))
    if not prices and not ingredients:
        raise not_found("import_not_found", "No encontramos esa importación")

    if prices:
        used = db.scalar(select(exists().where(QuoteLine.ingredient_price_id.in_([p.id for p in prices]))))
        if used:
            raise ProblemError(
                409, "import_in_use", "Esos precios ya se usaron en una cotización; no se pueden deshacer"
            )
        keys = {(p.ingredient_id, p.supplier_id, p.package_label) for p in prices}
        db.execute(delete(IngredientPrice).where(IngredientPrice.import_batch_id == batch_id))
        db.flush()
        for ing_id, sup_id, label in keys:  # se vuelve a la versión anterior, si había
            same = (
                (IngredientPrice.ingredient_id == ing_id)
                & (IngredientPrice.supplier_id == sup_id)
                & (IngredientPrice.package_label == label)
            )
            if db.scalar(select(exists().where(same, IngredientPrice.is_current))):
                continue
            latest = db.scalar(select(IngredientPrice).where(same).order_by(IngredientPrice.created_at.desc()).limit(1))
            if latest is not None:
                latest.is_current = True

    if ingredients:
        ids = [i.id for i in ingredients]
        in_use = set(db.scalars(select(RecipeLine.ingredient_id).where(RecipeLine.ingredient_id.in_(ids))))
        in_use |= set(
            db.scalars(
                select(IngredientPrice.ingredient_id).where(
                    IngredientPrice.ingredient_id.in_(ids),
                    (IngredientPrice.import_batch_id != batch_id) | IngredientPrice.import_batch_id.is_(None),
                )
            )
        )
        in_use |= set(
            db.scalars(
                select(StockMovement.ingredient_id).where(
                    StockMovement.ingredient_id.in_(ids), StockMovement.reason != MovementReason.IMPORT
                )
            )
        )
        if in_use:
            names = sorted(i.name for i in ingredients if i.id in in_use)
            db.rollback()
            raise ProblemError(409, "import_in_use", "Algunos insumos importados ya se usaron", ", ".join(names))
        db.execute(delete(Ingredient).where(Ingredient.id.in_(ids)))

    bump(db, DataDomain.INVENTORY, DataDomain.SUPPLIERS, DataDomain.RECIPES)
    db.commit()
    return UndoResult(ingredients_deleted=len(ingredients), prices_deleted=len(prices))

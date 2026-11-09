import uuid

from fastapi import APIRouter, Response, status

from app.core.tenancy import CurrentUserDep, TenantDB
from app.db.models import IngredientPrice, Supplier
from app.modules.suppliers import service
from app.modules.suppliers.schemas import (
    PriceComparison,
    PriceCreate,
    PriceOut,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)

router = APIRouter(tags=["proveedores y precios"])


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(_user: CurrentUserDep, db: TenantDB, include_inactive: bool = False) -> list[Supplier]:
    return service.list_suppliers(db, include_inactive)


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(data: SupplierCreate, _user: CurrentUserDep, db: TenantDB) -> Supplier:
    supplier = service.create_supplier(db, data)
    db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> Supplier:
    return service.get_supplier(db, supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: uuid.UUID, data: SupplierUpdate, _user: CurrentUserDep, db: TenantDB) -> Supplier:
    return service.update_supplier(db, supplier_id, data)


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_supplier(supplier_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> Response:
    """Desactiva el proveedor: sus precios dejan de compararse, pero las cotizaciones antiguas se conservan."""
    service.update_supplier(db, supplier_id, SupplierUpdate(is_active=False))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/prices", response_model=list[PriceOut])
def list_prices(
    _user: CurrentUserDep,
    db: TenantDB,
    ingredient_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    include_history: bool = False,
) -> list[IngredientPrice]:
    return service.list_prices(db, ingredient_id, supplier_id, include_history)


@router.post("/prices", response_model=PriceOut, status_code=status.HTTP_201_CREATED)
def create_price(data: PriceCreate, _user: CurrentUserDep, db: TenantDB) -> IngredientPrice:
    """Registra un precio. Si ya había uno vigente para la misma presentación, queda como historial."""
    price = service.create_price(db, data)
    db.refresh(price)
    return price


@router.get("/ingredients/{ingredient_id}/prices", response_model=PriceComparison)
def compare_prices(ingredient_id: uuid.UUID, _user: CurrentUserDep, db: TenantDB) -> PriceComparison:
    """Precios vigentes de un insumo, normalizados por kg, L o unidad y con IVA, del más barato al más caro."""
    return service.compare_prices(db, ingredient_id)

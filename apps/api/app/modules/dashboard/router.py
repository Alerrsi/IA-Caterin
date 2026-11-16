"""Tablero del negocio con gráficos (T17). Solo la dueña."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.tenancy import OwnerDep, TenantDB
from app.modules.dashboard import service
from app.modules.dashboard.schemas import Dashboard

router = APIRouter(prefix="/dashboard", tags=["tablero"])


@router.get("", response_model=Dashboard)
def get_dashboard(
    _owner: OwnerDep,
    db: TenantDB,
    months: Annotated[int, Query(ge=1, le=12, description="Meses hacia atrás, incluido el mes en curso")] = 6,
) -> Dashboard:
    """Venta por mes, margen sobre insumos, productos más pedidos, próximos eventos, compras estimadas por proveedor e
    insumos bajo el mínimo. Cifras calculadas en código (ADR-002); supuestos en docs/tasks/T17-tablero.md."""
    return service.build_dashboard(db, months)

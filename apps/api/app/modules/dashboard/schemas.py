"""Respuesta del tablero del negocio (T17). Dinero en CLP enteros; cantidades en texto decimal, como en la API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class DashboardPeriod(BaseModel):
    months: int
    date_from: date = Field(description="Primer día del primer mes incluido (America/Santiago)")
    date_to: date = Field(description="Último día del mes en curso")
    today: date
    timezone: str = "America/Santiago"


class DashboardKpis(BaseModel):
    sales_total_clp: int = Field(description="Venta con IVA de los pedidos vendidos del periodo")
    sales_net_clp: int = Field(description="Venta neta (sin IVA)")
    ingredients_cost_clp: int
    margin_clp: int = Field(description="Venta neta menos costo de insumos. No incluye sueldos, arriendo ni gas")
    margin_pct: float | None = Field(description="Margen sobre la venta neta, 0 a 100; null sin ventas")
    sold_orders: int = Field(description="Pedidos confirmados o entregados con cotización aceptada")
    avg_ticket_clp: int | None = Field(description="Venta con IVA promedio por pedido vendido; null sin ventas")
    orders_without_quote: int = Field(description="Pedidos confirmados o entregados sin cotización aceptada")
    pending_requests: int = Field(description="Solicitudes del portal por responder (todas, sin periodo)")
    upcoming_7d: int = Field(description="Pedidos confirmados o por confirmar con evento en los próximos 7 días")
    low_stock: int = Field(description="Insumos activos bajo su stock mínimo")


class MonthSales(BaseModel):
    month: str = Field(description="AAAA-MM")
    orders: int
    net_clp: int
    ingredients_cost_clp: int
    margin_clp: int
    total_clp: int


class StatusCount(BaseModel):
    status: str
    orders: int


class TopProduct(BaseModel):
    recipe_id: uuid.UUID
    name: str
    units: str = Field(description="Unidades pedidas (unidad y porción = 1, docena = 12)")
    orders: int


class TopProducts(BaseModel):
    items: list[TopProduct]
    excluded_lines: int = Field(description="Líneas en g, kg, ml o L: no se suman como unidades")


class DayLoad(BaseModel):
    day: date
    confirmed: int
    pending: int = Field(description="Borradores y solicitudes del portal")
    guests: int


class SupplierSpend(BaseModel):
    supplier_id: uuid.UUID | None = Field(description="null en la fila «Otros»")
    name: str
    amount_clp: int


class LowStockItem(BaseModel):
    ingredient_id: uuid.UUID
    name: str
    base_unit: str
    stock_qty: str
    min_stock_qty: str
    pct_of_min: float = Field(description="Stock como porcentaje del mínimo, 0 a 100")


class LowStock(BaseModel):
    items: list[LowStockItem]
    total: int


class Dashboard(BaseModel):
    period: DashboardPeriod
    kpis: DashboardKpis
    sales_by_month: list[MonthSales]
    orders_by_status: list[StatusCount]
    top_products: TopProducts
    upcoming_by_day: list[DayLoad]
    spend_by_supplier: list[SupplierSpend]
    low_stock: LowStock
    generated_at: datetime

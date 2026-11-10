"""Pyme de demostración GRANDE y SINTÉTICA que llena todas las tablas (AGENTS.md, sección 10).

Uso (con la API y Ollama arriba, para vectorizar documentos y fichas):

    docker exec caterin-api-1 python -m app.db.demo_full

- Crea "Banquetería Volcán Llaima (demo)": ~95 insumos, 10 proveedores con historial de precios, 30 recetas,
  ~200 pedidos en 8 meses (pasados y futuros) con sus cotizaciones, movimientos de stock, producción, caja,
  documentos indexados, fichas del RAG, preguntas al asistente, métricas y clientes del portal con solicitudes.
- No toca las pymes de `seed.py` (Aromos y Lago): las pruebas y los sets de evaluación dependen de ellas.
- Todo es inventado: nombres, clientes, precios y tiempos. Los eventos de métricas llevan `"synthetic": true` y la
  pyme es `is_demo`, así el panel global puede excluirlos (`exclude_demo`).
- Los cálculos usan los mismos servicios de la app: cotizaciones con `quotes.service.create_quote`, solicitudes con
  el portal, documentos con `documents.service.upload` y preguntas con `assistant.service.ask` (sin LLM).
- Es reproducible (semilla fija) e idempotente: si la pyme ya existe, no hace nada.
"""

import logging
import os
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embeddings import get_embeddings
from app.core.llm import get_llm
from app.core.security import hash_password
from app.core.tenancy import CurrentUser, open_tenant_session
from app.db.enums import (
    BaseUnit,
    CashKind,
    DataDomain,
    MetricKind,
    MovementReason,
    OrderSource,
    OrderStatus,
    OrderUnit,
    PriceSourceKind,
    QuoteStatus,
    Role,
)
from app.db.models import (
    AssistantInteraction,
    CashMovement,
    DataVersion,
    Ingredient,
    IngredientPrice,
    LoginAttempt,
    MetricEvent,
    Order,
    OrderLine,
    ProductionRecord,
    Pyme,
    Quote,
    Recipe,
    RecipeLine,
    StockMovement,
    Supplier,
    User,
)
from app.db.seed import DEFAULT_DEMO_PASSWORD, DEMO_PASSWORD_ENV
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

PYME_NAME = "Banquetería Volcán Llaima (demo)"
OWNER_EMAIL = "duena.llaima@demo.local"
DOCS_DIR = Path(__file__).parent / "demo_docs"
SEED = 2026
G, ML, U = BaseUnit.GRAM, BaseUnit.MILLILITER, BaseUnit.UNIT

# --------------------------------------------------------------------------- catálogo (inventado)

# clave: (nombre, días de despacho 1=lunes, teléfono, correo, notas)
SUPPLIERS = {
    "molino": (
        "Molinos del Cautín (demo)",
        [1, 4],
        "+56 9 0000 1101",
        "pedidos@molinoscautin.demo",
        "Pedido mínimo $60.000",
    ),
    "lacteos": (
        "Lácteos Malleco (demo)",
        [2, 5],
        "+56 9 0000 1102",
        "ventas@lacteosmalleco.demo",
        "Camión refrigerado",
    ),
    "carnes": ("Carnes Pitrufquén (demo)", [1, 3, 5], "+56 9 0000 1103", None, "Despacho temprano, antes de las 9:00"),
    "feria": ("Feria Pinto Hortalizas (demo)", [1, 2, 3, 4, 5, 6], "+56 9 0000 1104", None, "Pago contra entrega"),
    "pescados": ("Pescadería Puerto Saavedra (demo)", [3, 6], "+56 9 0000 1105", None, None),
    "mayorista": (
        "Distribuidora Araucanía Mayorista (demo)",
        [2, 4],
        "+56 9 0000 1106",
        "contacto@araucaniamayorista.demo",
        None,
    ),
    "pan": ("Panificadora Labranza (demo)", [1, 2, 3, 4, 5, 6], "+56 9 0000 1107", None, "Encargar con 24 h"),
    "envases": ("Envases del Sur (demo)", [3], None, "ventas@envasesdelsur.demo", None),
    "bosque": ("Frutos del Bosque Curacautín (demo)", [5], "+56 9 0000 1109", None, "Murta y maqui de temporada"),
    "huevos": ("Huevos Freire (demo)", [2, 5], "+56 9 0000 1110", None, None),
}

# (nombre, unidad, categoría, merma %, mínimo, [(proveedor, presentación, cantidad en unidad base, precio CLP)])
Opt = tuple[str, str, int, int]
INGREDIENTS: list[tuple[str, BaseUnit, str, int | None, int | None, list[Opt]]] = [
    (
        "Harina sin polvos",
        G,
        "Abarrotes",
        None,
        10000,
        [("molino", "saco 25 kg", 25000, 22990), ("mayorista", "bolsa 1 kg", 1000, 1190)],
    ),
    (
        "Harina con polvos",
        G,
        "Abarrotes",
        None,
        3000,
        [("molino", "bolsa 1 kg", 1000, 1290), ("mayorista", "bolsa 1 kg", 1000, 1390)],
    ),
    (
        "Azúcar",
        G,
        "Abarrotes",
        None,
        5000,
        [("mayorista", "bolsa 1 kg", 1000, 1150), ("molino", "saco 25 kg", 25000, 23990)],
    ),
    ("Azúcar flor", G, "Abarrotes", None, None, [("mayorista", "bolsa 1 kg", 1000, 1790)]),
    ("Sal", G, "Abarrotes", None, 1000, [("mayorista", "bolsa 1 kg", 1000, 590)]),
    (
        "Aceite vegetal",
        ML,
        "Abarrotes",
        None,
        5000,
        [("mayorista", "bidón 5 L", 5000, 9990), ("molino", "botella 1 L", 1000, 2390)],
    ),
    ("Aceite de oliva", ML, "Abarrotes", None, None, [("mayorista", "botella 1 L", 1000, 7990)]),
    ("Manteca", G, "Abarrotes", None, 2000, [("molino", "paquete 1 kg", 1000, 2890)]),
    ("Polvos de hornear", G, "Abarrotes", None, None, [("mayorista", "tarro 250 g", 250, 1490)]),
    ("Maicena", G, "Abarrotes", None, None, [("mayorista", "caja 400 g", 400, 1290)]),
    ("Chocolate cobertura", G, "Abarrotes", None, None, [("mayorista", "bolsa 1 kg", 1000, 8990)]),
    ("Cacao amargo", G, "Abarrotes", None, None, [("mayorista", "bolsa 500 g", 500, 4590)]),
    ("Esencia de vainilla", ML, "Abarrotes", None, None, [("mayorista", "frasco 500 ml", 500, 3490)]),
    ("Leche condensada", G, "Abarrotes", None, None, [("mayorista", "lata 397 g", 397, 1890)]),
    ("Leche evaporada", G, "Abarrotes", None, None, [("mayorista", "lata 400 g", 400, 1490)]),
    ("Mayonesa", G, "Abarrotes", None, 1000, [("mayorista", "balde 1 kg", 1000, 3990)]),
    ("Vinagre", ML, "Abarrotes", None, None, [("mayorista", "botella 1 L", 1000, 990)]),
    ("Aceituna negra", U, "Abarrotes", None, 100, [("mayorista", "frasco 100 unidades", 100, 3490)]),
    ("Pasas", G, "Abarrotes", None, None, [("mayorista", "bolsa 1 kg", 1000, 4590)]),
    ("Mote de trigo", G, "Abarrotes", None, None, [("mayorista", "bolsa 1 kg", 1000, 1690)]),
    ("Huesillo", G, "Abarrotes", None, None, [("mayorista", "bolsa 1 kg", 1000, 4290)]),
    ("Atún en lata", G, "Abarrotes", None, None, [("mayorista", "lata 170 g", 170, 1290)]),
    (
        "Manjar",
        G,
        "Lácteos y huevos",
        None,
        1000,
        [("lacteos", "pote 1 kg", 1000, 3690), ("mayorista", "pote 1 kg", 1000, 3890)],
    ),
    ("Comino", G, "Especias", None, None, [("mayorista", "sobre 100 g", 100, 990)]),
    ("Ají de color", G, "Especias", None, None, [("mayorista", "sobre 100 g", 100, 990)]),
    ("Orégano", G, "Especias", None, None, [("mayorista", "sobre 50 g", 50, 690)]),
    ("Pimienta", G, "Especias", None, None, [("mayorista", "sobre 100 g", 100, 1590)]),
    ("Merkén", G, "Especias", None, None, [("bosque", "sobre 100 g", 100, 1990)]),
    ("Canela", G, "Especias", None, None, [("mayorista", "sobre 50 g", 50, 890)]),
    (
        "Leche",
        ML,
        "Lácteos y huevos",
        None,
        4000,
        [("lacteos", "caja 1 L", 1000, 1090), ("mayorista", "caja 1 L", 1000, 1150)],
    ),
    ("Crema de leche", ML, "Lácteos y huevos", None, 2000, [("lacteos", "caja 1 L", 1000, 4290)]),
    (
        "Mantequilla",
        G,
        "Lácteos y huevos",
        None,
        1000,
        [("lacteos", "barra 250 g", 250, 2190), ("mayorista", "pan 500 g", 500, 4290)],
    ),
    ("Queso mantecoso", G, "Lácteos y huevos", None, 3000, [("lacteos", "bloque 1 kg", 1000, 8990)]),
    ("Queso gauda laminado", G, "Lácteos y huevos", None, 1000, [("lacteos", "paquete 1 kg", 1000, 9490)]),
    ("Queso crema", G, "Lácteos y huevos", None, 1000, [("lacteos", "pote 1 kg", 1000, 7490)]),
    ("Queso de cabra", G, "Lácteos y huevos", None, None, [("lacteos", "rollo 200 g", 200, 3990)]),
    ("Queso parmesano", G, "Lácteos y huevos", None, None, [("lacteos", "bolsa 250 g", 250, 4990)]),
    ("Quesillo", G, "Lácteos y huevos", None, None, [("lacteos", "unidad 500 g", 500, 2990)]),
    ("Yogur natural", G, "Lácteos y huevos", None, None, [("lacteos", "pote 1 kg", 1000, 2490)]),
    (
        "Huevo",
        U,
        "Lácteos y huevos",
        None,
        60,
        [("huevos", "bandeja 30 unidades", 30, 6990), ("mayorista", "bandeja 12 unidades", 12, 3290)],
    ),
    ("Huevo de codorniz", U, "Lácteos y huevos", None, None, [("huevos", "caja 24 unidades", 24, 2990)]),
    ("Carne molida", G, "Carnes", None, 3000, [("carnes", "bolsa 1 kg", 1000, 8490)]),
    ("Posta negra", G, "Carnes", 5, None, [("carnes", "trozo 1 kg", 1000, 10990)]),
    ("Pechuga de pollo", G, "Carnes", 5, 3000, [("carnes", "bandeja 1 kg", 1000, 5990)]),
    ("Trutro deshuesado", G, "Carnes", 5, None, [("carnes", "bandeja 1 kg", 1000, 4990)]),
    ("Lomo de cerdo", G, "Carnes", 5, None, [("carnes", "trozo 1 kg", 1000, 7490)]),
    ("Jamón pierna", G, "Carnes", None, 1000, [("carnes", "paquete 1 kg", 1000, 7990)]),
    ("Salame", G, "Carnes", None, None, [("carnes", "paquete 500 g", 500, 5490)]),
    ("Longaniza", G, "Carnes", None, None, [("carnes", "paquete 1 kg", 1000, 6490)]),
    ("Tocino", G, "Carnes", None, None, [("carnes", "paquete 500 g", 500, 4290)]),
    ("Salmón ahumado", G, "Pescados y mariscos", None, 500, [("pescados", "paquete 1 kg", 1000, 22990)]),
    ("Salmón fresco", G, "Pescados y mariscos", 10, None, [("pescados", "filete 1 kg", 1000, 12990)]),
    ("Camarón ecuatoriano", G, "Pescados y mariscos", None, 500, [("pescados", "bolsa 1 kg", 1000, 13990)]),
    ("Reineta", G, "Pescados y mariscos", 10, None, [("pescados", "filete 1 kg", 1000, 8990)]),
    ("Choritos", G, "Pescados y mariscos", 30, None, [("pescados", "malla 1 kg", 1000, 2990)]),
    (
        "Cebolla",
        G,
        "Verduras",
        10,
        5000,
        [("feria", "malla 10 kg", 10000, 6990), ("mayorista", "malla 3 kg", 3000, 2990)],
    ),
    ("Cebolla morada", G, "Verduras", 10, None, [("feria", "bolsa 1 kg", 1000, 1290)]),
    ("Tomate", G, "Verduras", 5, 3000, [("feria", "caja 1 kg", 1000, 1490)]),
    ("Tomate cherry", U, "Verduras", None, None, [("feria", "bandeja 100 unidades", 100, 2490)]),
    ("Palta hass", G, "Verduras", 30, 1000, [("feria", "bolsa 1 kg", 1000, 4990)]),
    ("Lechuga", U, "Verduras", None, None, [("feria", "unidad", 1, 890)]),
    ("Pepino", U, "Verduras", None, None, [("feria", "unidad", 1, 590)]),
    ("Zanahoria", G, "Verduras", 10, None, [("feria", "bolsa 1 kg", 1000, 790)]),
    ("Papa", G, "Verduras", 15, None, [("feria", "saco 25 kg", 25000, 9990)]),
    ("Choclo desgranado", G, "Verduras", None, 1000, [("mayorista", "bolsa 1 kg", 1000, 2490)]),
    ("Zapallo", G, "Verduras", 20, None, [("feria", "trozo 1 kg", 1000, 890)]),
    ("Champiñón", G, "Verduras", 5, None, [("feria", "bandeja 500 g", 500, 2290)]),
    ("Pimentón rojo", G, "Verduras", 15, None, [("feria", "bolsa 1 kg", 1000, 2990)]),
    ("Ajo", G, "Verduras", 10, None, [("feria", "malla 1 kg", 1000, 4990)]),
    ("Cilantro", G, "Verduras", None, None, [("feria", "atado 100 g", 100, 590)]),
    ("Perejil", G, "Verduras", None, None, [("feria", "atado 100 g", 100, 590)]),
    ("Ciboulette", G, "Verduras", None, None, [("feria", "atado 50 g", 50, 790)]),
    ("Albahaca", G, "Verduras", None, None, [("feria", "atado 50 g", 50, 990)]),
    ("Eneldo", G, "Verduras", None, None, [("feria", "atado 50 g", 50, 790)]),
    ("Rúcula", G, "Verduras", None, None, [("feria", "bolsa 200 g", 200, 1490)]),
    ("Apio", U, "Verduras", None, None, [("feria", "unidad", 1, 1290)]),
    ("Betarraga", G, "Verduras", 15, None, [("feria", "bolsa 1 kg", 1000, 990)]),
    ("Limón", U, "Frutas", None, 30, [("feria", "malla 10 unidades", 10, 1990)]),
    ("Manzana", G, "Frutas", 15, None, [("feria", "bolsa 1 kg", 1000, 1290)]),
    ("Frutilla", G, "Frutas", 10, None, [("feria", "caja 1 kg", 1000, 3490)]),
    ("Piña", U, "Frutas", None, None, [("feria", "unidad", 1, 2490)]),
    ("Kiwi", G, "Frutas", 10, None, [("feria", "bolsa 1 kg", 1000, 2290)]),
    ("Uva", G, "Frutas", 5, None, [("feria", "bolsa 1 kg", 1000, 2490)]),
    ("Murta", G, "Frutos del bosque", None, None, [("bosque", "bolsa 500 g", 500, 5990)]),
    ("Maqui", G, "Frutos del bosque", None, None, [("bosque", "bolsa 500 g", 500, 6490)]),
    (
        "Frambuesa congelada",
        G,
        "Frutos del bosque",
        None,
        None,
        [("bosque", "bolsa 1 kg", 1000, 4990), ("mayorista", "bolsa 1 kg", 1000, 5290)],
    ),
    ("Arándano", G, "Frutos del bosque", None, None, [("bosque", "bolsa 500 g", 500, 3990)]),
    ("Nuez", G, "Frutos del bosque", None, None, [("bosque", "bolsa 1 kg", 1000, 12990)]),
    ("Avellana europea", G, "Frutos del bosque", None, None, [("bosque", "bolsa 500 g", 500, 6990)]),
    ("Pan de miga", U, "Panadería", None, 20, [("pan", "paquete 20 rebanadas", 20, 3990)]),
    ("Pan de cóctel", U, "Panadería", None, 96, [("pan", "bolsa 48 unidades", 48, 3990)]),
    ("Pan de hamburguesa mini", U, "Panadería", None, None, [("pan", "bolsa 24 unidades", 24, 3490)]),
    (
        "Masa de hojaldre",
        G,
        "Panadería",
        None,
        1000,
        [("pan", "paquete 1 kg", 1000, 4590), ("mayorista", "paquete 1 kg", 1000, 4890)],
    ),
    ("Palito de brocheta", U, "Desechables", None, 200, [("envases", "paquete 100 unidades", 100, 1490)]),
    ("Pirotín", U, "Desechables", None, 200, [("envases", "paquete 200 unidades", 200, 2490)]),
    ("Vaso plástico 200 ml", U, "Desechables", None, 100, [("envases", "paquete 50 unidades", 50, 1990)]),
    ("Servilleta de cóctel", U, "Desechables", None, 300, [("envases", "paquete 300 unidades", 300, 2490)]),
    ("Bandeja de cartón", U, "Desechables", None, 20, [("envases", "paquete 25 unidades", 25, 4990)]),
    ("Caja de torta", U, "Desechables", None, None, [("envases", "paquete 10 unidades", 10, 5990)]),
]
# Sin uso en recetas y desactivados: aparecen como historial del inventario.
INACTIVE = {"Huevo de codorniz", "Choritos"}


@dataclass(frozen=True)
class RecipeDef:
    name: str
    yield_qty: int
    unit: BaseUnit
    lines: list[tuple[str, int]]
    vision: str | None = None
    final: bool = True


RECIPES = [
    RecipeDef(
        "Empanadas de pino",
        12,
        U,
        [
            ("Harina sin polvos", 600),
            ("Manteca", 100),
            ("Sal", 10),
            ("Carne molida", 700),
            ("Cebolla", 800),
            ("Huevo", 3),
            ("Aceituna negra", 12),
            ("Pasas", 40),
            ("Comino", 3),
            ("Ají de color", 5),
            ("Aceite vegetal", 50),
        ],
        "empanada_pino",
    ),
    RecipeDef(
        "Empanadas de queso",
        12,
        U,
        [("Harina sin polvos", 550), ("Manteca", 90), ("Queso mantecoso", 650), ("Sal", 8), ("Aceite vegetal", 600)],
        "empanada_queso",
    ),
    RecipeDef(
        "Empanadas napolitanas",
        12,
        U,
        [
            ("Harina sin polvos", 550),
            ("Manteca", 90),
            ("Queso mantecoso", 400),
            ("Jamón pierna", 250),
            ("Tomate", 300),
            ("Orégano", 3),
        ],
    ),
    RecipeDef(
        "Empanadas de camarón queso",
        12,
        U,
        [
            ("Harina sin polvos", 550),
            ("Manteca", 90),
            ("Camarón ecuatoriano", 400),
            ("Queso mantecoso", 400),
            ("Ajo", 10),
            ("Cilantro", 10),
        ],
    ),
    RecipeDef(
        "Sopaipillas",
        24,
        U,
        [("Harina con polvos", 500), ("Zapallo", 300), ("Manteca", 80), ("Sal", 8), ("Aceite vegetal", 800)],
        "sopaipilla",
    ),
    RecipeDef(
        "Canapés de salmón",
        24,
        U,
        [("Pan de cóctel", 24), ("Queso crema", 240), ("Salmón ahumado", 300), ("Eneldo", 5), ("Limón", 1)],
        "canape_salmon",
    ),
    RecipeDef(
        "Canapés de ave palta",
        24,
        U,
        [("Pan de cóctel", 24), ("Pechuga de pollo", 400), ("Palta hass", 400), ("Mayonesa", 100), ("Limón", 1)],
    ),
    RecipeDef(
        "Canapés de queso de cabra y murta",
        24,
        U,
        [("Pan de cóctel", 24), ("Queso de cabra", 300), ("Murta", 150), ("Azúcar", 50), ("Nuez", 60)],
    ),
    RecipeDef(
        "Brochetas de pollo",
        12,
        U,
        [
            ("Pechuga de pollo", 800),
            ("Pimentón rojo", 300),
            ("Cebolla morada", 200),
            ("Palito de brocheta", 12),
            ("Aceite de oliva", 30),
            ("Merkén", 3),
        ],
        "brocheta_pollo",
    ),
    RecipeDef(
        "Brochetas caprese",
        24,
        U,
        [
            ("Tomate cherry", 48),
            ("Quesillo", 300),
            ("Albahaca", 20),
            ("Aceite de oliva", 30),
            ("Palito de brocheta", 24),
        ],
    ),
    RecipeDef(
        "Brochetas de fruta",
        24,
        U,
        [("Frutilla", 400), ("Piña", 1), ("Kiwi", 400), ("Uva", 400), ("Palito de brocheta", 24)],
    ),
    RecipeDef(
        "Mini quiches",
        24,
        U,
        [
            ("Masa de hojaldre", 600),
            ("Huevo", 6),
            ("Crema de leche", 400),
            ("Queso gauda laminado", 200),
            ("Tocino", 200),
            ("Cebolla", 150),
        ],
        "mini_quiche",
    ),
    RecipeDef(
        "Sándwich de ave mayo", 20, U, [("Pan de miga", 10), ("Pechuga de pollo", 500), ("Mayonesa", 150), ("Apio", 1)]
    ),
    RecipeDef(
        "Sándwich de jamón queso",
        20,
        U,
        [("Pan de miga", 10), ("Jamón pierna", 300), ("Queso gauda laminado", 300), ("Mantequilla", 80)],
    ),
    RecipeDef(
        "Sándwich de ave pimentón",
        20,
        U,
        [("Pan de miga", 10), ("Pechuga de pollo", 450), ("Pimentón rojo", 200), ("Mayonesa", 120)],
    ),
    RecipeDef(
        "Mini hamburguesas",
        24,
        U,
        [
            ("Pan de hamburguesa mini", 24),
            ("Carne molida", 1000),
            ("Queso gauda laminado", 240),
            ("Tomate", 300),
            ("Lechuga", 1),
            ("Mayonesa", 100),
        ],
    ),
    RecipeDef(
        "Choripanes de cóctel",
        24,
        U,
        [("Pan de cóctel", 24), ("Longaniza", 800), ("Cebolla", 200), ("Tomate", 200), ("Cilantro", 20)],
    ),
    RecipeDef(
        "Tapaditos de salmón fresco",
        24,
        U,
        [("Pan de cóctel", 24), ("Salmón fresco", 500), ("Limón", 3), ("Cebolla morada", 100), ("Ciboulette", 10)],
    ),
    RecipeDef(
        "Pie de limón",
        1,
        U,
        [
            ("Harina sin polvos", 250),
            ("Mantequilla", 125),
            ("Azúcar", 200),
            ("Huevo", 4),
            ("Limón", 5),
            ("Leche condensada", 397),
        ],
    ),
    RecipeDef(
        "Kuchen de murta",
        1,
        U,
        [
            ("Harina sin polvos", 300),
            ("Mantequilla", 150),
            ("Azúcar", 200),
            ("Huevo", 3),
            ("Murta", 500),
            ("Crema de leche", 200),
        ],
    ),
    RecipeDef(
        "Kuchen de manzana",
        1,
        U,
        [
            ("Harina sin polvos", 300),
            ("Mantequilla", 150),
            ("Azúcar", 220),
            ("Huevo", 3),
            ("Manzana", 800),
            ("Canela", 5),
            ("Crema de leche", 200),
        ],
    ),
    RecipeDef(
        "Torta tres leches",
        1,
        U,
        [
            ("Harina con polvos", 250),
            ("Huevo", 6),
            ("Azúcar", 250),
            ("Leche", 500),
            ("Leche condensada", 397),
            ("Leche evaporada", 400),
            ("Crema de leche", 300),
            ("Caja de torta", 1),
        ],
    ),
    RecipeDef(
        "Torta de chocolate y manjar",
        1,
        U,
        [
            ("Harina con polvos", 300),
            ("Cacao amargo", 80),
            ("Chocolate cobertura", 300),
            ("Huevo", 5),
            ("Azúcar", 300),
            ("Mantequilla", 200),
            ("Crema de leche", 400),
            ("Manjar", 500),
            ("Caja de torta", 1),
        ],
    ),
    RecipeDef(
        "Alfajores",
        24,
        U,
        [
            ("Maicena", 200),
            ("Harina sin polvos", 150),
            ("Mantequilla", 150),
            ("Azúcar flor", 80),
            ("Huevo", 3),
            ("Manjar", 500),
            ("Pirotín", 24),
        ],
    ),
    RecipeDef(
        "Mote con huesillo", 3000, ML, [("Mote de trigo", 300), ("Huesillo", 400), ("Azúcar", 400), ("Canela", 3)]
    ),
    RecipeDef(
        "Ensalada chilena",
        1000,
        G,
        [("Tomate", 700), ("Cebolla", 250), ("Cilantro", 15), ("Aceite vegetal", 30), ("Sal", 5)],
    ),
    RecipeDef(
        "Pastel de choclo individual",
        6,
        U,
        [
            ("Choclo desgranado", 1200),
            ("Carne molida", 500),
            ("Cebolla", 400),
            ("Pechuga de pollo", 300),
            ("Huevo", 3),
            ("Aceituna negra", 6),
            ("Albahaca", 10),
            ("Azúcar", 30),
            ("Leche", 200),
        ],
    ),
    RecipeDef(
        "Ceviche de reineta",
        1000,
        G,
        [("Reineta", 700), ("Limón", 10), ("Cebolla morada", 200), ("Cilantro", 20), ("Merkén", 2)],
    ),
    # Preparaciones base (no se venden solas; no aparecen en el portal de clientes)
    RecipeDef(
        "Masa de empanadas",
        1000,
        G,
        [("Harina sin polvos", 800), ("Manteca", 150), ("Sal", 12), ("Leche", 200)],
        final=False,
    ),
    RecipeDef(
        "Pebre",
        1000,
        G,
        [("Tomate", 600), ("Cebolla", 200), ("Cilantro", 30), ("Aceite vegetal", 50), ("Vinagre", 20)],
        final=False,
    ),
]

CUSTOMER_KINDS = [
    ("Constructora Demo Ñielol", "reunión de directorio"),
    ("Colegio Demo Los Avellanos", "graduación"),
    ("Clínica Demo Alemana Sur", "aniversario"),
    ("Municipalidad Demo de Vilcún", "ceremonia"),
    ("Universidad Demo de la Frontera", "seminario"),
    ("Familia Demo Rivas", "matrimonio"),
    ("Familia Demo Huenchullán", "bautizo"),
    ("Familia Demo Saavedra", "cumpleaños 50"),
    ("Agrícola Demo Malleco", "día de campo"),
    ("Hotel Demo Llaima", "cóctel de bienvenida"),
    ("Estudio Demo Contable Sur", "fiesta de fin de año"),
    ("Club Demo Deportivo Temuco", "premiación"),
    ("Cooperativa Demo Lautaro", "asamblea"),
    ("Familia Demo Pichún", "primera comunión"),
    ("Banco Demo del Sur", "desayuno corporativo"),
    ("Junta de Vecinos Demo Amanecer", "once comunitaria"),
]
TEXT_MSG = "Hola, para el {d} somos {g} personas. Necesito {items}. Gracias (MENSAJE SINTÉTICO)."

ASSISTANT_QUESTIONS = [
    "¿cuánto queso crema me queda?",
    "¿qué me falta comprar?",
    "¿cuánto cuesta la receta de empanadas de pino?",
    "¿qué pedidos tengo esta semana?",
    "¿dónde compro más barata la harina?",
    "¿qué días despacha Lácteos Malleco?",
    "¿qué lácteos tengo?",
    "¿cuál es el pedido mínimo de Molinos del Cautín?",
    "¿a qué temperatura se guarda el helado?",
    "¿cuánto cuesta el despacho a Labranza?",
    "¿las brochetas de pollo tienen gluten?",
    "¿cuánto produje esta semana?",
    "¿qué recetas llevan murta?",
    "¿cuántos proveedores tengo?",
    "¿cuánto me queda de pechuga de pollo?",
    "¿quién me vende el salmón ahumado?",
    "¿cuánto cuesta el kuchen de murta?",
    "¿qué pedidos tengo el próximo mes?",
    "teléfono de Carnes Pitrufquén",
    "¿cuál es el correo de Envases del Sur?",
    "¿hasta cuándo se puede anular sin costo?",
    "¿el mote con huesillo es vegano?",
    "¿qué especias tengo?",
    "¿cuántas recetas tengo?",
    "¿dónde compro más barato el huevo?",
    "¿qué insumos están bajo el mínimo?",
    "¿cuánto abono se pide para reservar?",
    "¿cuánto cuesta la torta tres leches?",
    "¿qué frutos del bosque tengo?",
    "¿a qué temperatura va la cámara de carnes?",
    "¿qué proveedores despachan los sábados?",
    "¿cuánto produje este mes?",
    "¿cuánto me queda de harina?",
    "¿qué desechables tengo?",
    "¿la crema de leche cuánto dura?",
]
SURVEY_COMMENTS = [
    "Rápido para cotizar (SINTÉTICO)",
    "Me gustaría ver el margen por producto (SINTÉTICO)",
    None,
    None,
    "La lista de compras me ahorra tiempo (SINTÉTICO)",
    "El conteo con foto se equivocó en una bandeja (SINTÉTICO)",
]


def _q(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


class Builder:
    def __init__(self, session: Session, today: date) -> None:
        self.s = session
        self.today = today
        self.rng = random.Random(SEED)  # noqa: S311 - datos de demo reproducibles, no criptografía
        self.ingredients: dict[str, Ingredient] = {}
        self.suppliers: dict[str, Supplier] = {}
        self.cheapest: dict[str, tuple[str, int, int]] = {}  # insumo -> (proveedor, cantidad, precio)
        self.recipes: dict[str, Recipe] = {}
        self.defs = {r.name: r for r in RECIPES}
        self.movements: list[StockMovement] = []

    # ----------------------------------------------------------------- pyme, usuarias, catálogo
    def base(self, password_hash: str) -> None:
        pyme = Pyme(
            name=PYME_NAME,
            commune="Temuco",
            rut=None,
            default_waste_pct=Decimal(4),
            default_margin_pct=Decimal(45),
            quote_validity_days=10,
            is_demo=True,
            customer_code="llaima-demo-2026",
        )
        self.s.add(pyme)
        self.s.flush()
        self.pyme = pyme
        pid = pyme.id
        self.s.add_all(DataVersion(pyme_id=pid, domain=d, version=0) for d in DataDomain)
        staff = [
            (OWNER_EMAIL, "Dueña Demo Llaima", Role.OWNER),
            ("cocina.llaima@demo.local", "Jefa de Cocina Demo Llaima", Role.COLLABORATOR),
            ("ventas.llaima@demo.local", "Encargada de Ventas Demo Llaima", Role.COLLABORATOR),
        ]
        self.users = [User(pyme_id=pid, email=e, full_name=n, password_hash=password_hash, role=r) for e, n, r in staff]
        self.customers = [
            User(
                pyme_id=pid,
                email=f"cliente{i}.llaima@demo.local",
                full_name=f"{name} (SINTÉTICO)",
                password_hash=password_hash,
                role=Role.CUSTOMER,
            )
            for i, name in enumerate(
                [
                    "Camila Demo Torres",
                    "Rodrigo Demo Painemal",
                    "Javiera Demo Soto",
                    "Matías Demo Catrileo",
                    "Fernanda Demo Muñoz",
                    "Ignacio Demo Lagos",
                    "Valentina Demo Ancán",
                    "Tomás Demo Figueroa",
                ],
                start=1,
            )
        ]
        self.s.add_all([*self.users, *self.customers])
        self.s.flush()
        self.owner = self.users[0]
        self.owner_cu = CurrentUser(self.owner.id, pid, Role.OWNER, self.owner.email, self.owner.full_name)

    def catalog(self) -> None:
        pid, oid = self.pyme.id, self.owner.id
        for key, (name, days, phone, email, notes) in SUPPLIERS.items():
            self.suppliers[key] = Supplier(
                pyme_id=pid, created_by=oid, name=name, delivery_days=days, phone=phone, email=email, notes=notes
            )
        self.s.add_all(self.suppliers.values())
        for name, unit, cat, waste, min_qty, _ in INGREDIENTS:
            self.ingredients[name] = Ingredient(
                pyme_id=pid,
                created_by=oid,
                name=name,
                base_unit=unit,
                category=cat,
                waste_pct=Decimal(waste) if waste else None,
                min_stock_qty=Decimal(min_qty) if min_qty else None,
                stock_qty=Decimal(0),
                is_active=name not in INACTIVE,
            )
        self.s.add_all(self.ingredients.values())
        self.s.flush()

        # Precios: el vigente (últimas 3 semanas) y dos versiones anteriores más baratas (historial).
        for name, _unit, _cat, _waste, _min, options in INGREDIENTS:
            for key, label, qty, price in options:
                hist = [(170, 0.92), (90, 0.96), (self.rng.randint(3, 21), 1.0)]
                for i, (days_ago, factor) in enumerate(hist):
                    self.s.add(
                        IngredientPrice(
                            pyme_id=pid,
                            created_by=oid,
                            ingredient_id=self.ingredients[name].id,
                            supplier_id=self.suppliers[key].id,
                            package_label=label,
                            package_qty=Decimal(qty),
                            price_clp=Decimal(round(price * factor / 10) * 10),
                            includes_vat=True,
                            price_date=self.today - timedelta(days=days_ago),
                            source=PriceSourceKind.MANUAL if i < 2 else PriceSourceKind.CSV,
                            is_current=i == 2,
                        )
                    )
                per_unit = price / qty
                best = self.cheapest.get(name)
                if best is None or per_unit < best[2] / best[1]:
                    self.cheapest[name] = (key, qty, price)

        for r in RECIPES:
            recipe = Recipe(
                pyme_id=pid,
                created_by=oid,
                name=r.name,
                yield_qty=Decimal(r.yield_qty),
                yield_unit=r.unit,
                vision_class=r.vision,
                is_final_product=r.final,
                notes="Receta de demostración (SINTÉTICA)",
            )
            recipe.lines = [
                RecipeLine(pyme_id=pid, created_by=oid, ingredient_id=self.ingredients[n].id, qty=Decimal(q))
                for n, q in r.lines
            ]
            self.recipes[r.name] = recipe
            self.s.add(recipe)
        self.s.flush()

    # ----------------------------------------------------------------- pedidos
    def _line_for(self, recipe: str) -> tuple[Decimal, OrderUnit]:
        r = self.defs[recipe]
        if r.unit == ML:
            return Decimal(self.rng.choice([3, 5, 8, 10, 15])), OrderUnit.LITER
        if r.unit == G:
            return Decimal(self.rng.choice([2, 3, 4, 5, 8])), OrderUnit.KILOGRAM
        if r.yield_qty == 1:
            return Decimal(self.rng.choice([1, 1, 2, 3])), OrderUnit.UNIT
        if self.rng.random() < 0.5:
            return Decimal(self.rng.choice([3, 4, 5, 6, 8, 10, 12, 15, 20])), OrderUnit.DOZEN
        return Decimal(self.rng.choice([24, 36, 48, 60, 80, 100, 120, 150, 200])), OrderUnit.UNIT

    def _units(self, qty: Decimal, unit: OrderUnit) -> Decimal:
        return qty * {OrderUnit.DOZEN: 12, OrderUnit.KILOGRAM: 1000, OrderUnit.LITER: 1000}.get(unit, 1)

    def orders(self) -> None:
        pid, oid = self.pyme.id, self.owner.id
        finals = [r.name for r in RECIPES if r.final]
        popular = finals[:12]
        self.order_rows: list[Order] = []
        for _ in range(200):
            offset = self.rng.randint(-240, 60)
            event = self.today + timedelta(days=offset)
            if offset < -1:
                status = OrderStatus.DELIVERED if self.rng.random() < 0.88 else OrderStatus.CANCELLED
            elif offset <= 0:
                status = OrderStatus.CONFIRMED
            else:
                status = OrderStatus.CONFIRMED if self.rng.random() < 0.6 else OrderStatus.DRAFT
            customer, kind = self.rng.choice(CUSTOMER_KINDS)
            guests = self.rng.choice([15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 150, 200])
            products = self.rng.sample(popular if self.rng.random() < 0.7 else finals, self.rng.randint(1, 4))
            lines = [(p, *self._line_for(p)) for p in products]
            source = self.rng.choice([OrderSource.FORM, OrderSource.FORM, OrderSource.TEXT, OrderSource.LIST])
            raw = None
            if source == OrderSource.TEXT:
                items = ", ".join(
                    f"{q} {'docenas' if u == OrderUnit.DOZEN else u.value} de {p.lower()}" for p, q, u in lines
                )
                raw = TEXT_MSG.format(d=event.strftime("%d/%m"), g=guests, items=items)
            created = _at(
                event - timedelta(days=self.rng.randint(4, 30)), self.rng.randint(12, 22), self.rng.randint(0, 59)
            )
            order = Order(
                pyme_id=pid,
                created_by=self.rng.choice(self.users).id,
                customer_name=f"{customer} ({kind})",
                customer_contact=self.rng.choice([None, "contacto@cliente.demo", "+56 9 0000 2000"]),
                event_date=event,
                guests=guests,
                status=status,
                source=source,
                raw_text=raw,
                notes=self.rng.choice(
                    [None, None, "Retira en la cocina", "Despacho a las 18:00", "Sin cebolla en las brochetas"]
                ),
                created_at=created,
                updated_at=created,
            )
            order.lines = [
                OrderLine(
                    pyme_id=pid,
                    created_by=oid,
                    recipe_id=self.recipes[p].id,
                    position=i,
                    requested_name=p.lower(),
                    qty=q,
                    unit=u,
                )
                for i, (p, q, u) in enumerate(lines)
            ]
            self.s.add(order)
            self.order_rows.append(order)
        self.s.flush()

    def consumption(self, order: Order) -> dict[str, Decimal]:
        need: dict[str, Decimal] = {}
        for line in order.lines:
            r = next(d for d in RECIPES if self.recipes[d.name].id == line.recipe_id)
            factor = self._units(line.qty, line.unit) / Decimal(r.yield_qty)
            for ing, qty in r.lines:
                waste = self.ingredients[ing].waste_pct or Decimal(4)
                need[ing] = need.get(ing, Decimal(0)) + _q(Decimal(qty) * factor * (1 + waste / 100))
        return need

    # ----------------------------------------------------------------- stock, compras y caja
    def stock_and_cash(self) -> None:
        pid, oid = self.pyme.id, self.owner.id
        start = self.today - timedelta(days=245)
        consumed: dict[str, Decimal] = {n: Decimal(0) for n in self.ingredients}
        cash: list[CashMovement] = []
        for o in self.order_rows:
            if o.status != OrderStatus.DELIVERED or o.event_date is None:
                continue
            for ing_name, qty in self.consumption(o).items():
                consumed[ing_name] += qty
                self.movements.append(
                    StockMovement(
                        pyme_id=pid,
                        created_by=oid,
                        ingredient_id=self.ingredients[ing_name].id,
                        delta_qty=-qty,
                        reason=MovementReason.CONSUMPTION,
                        note="Consumo del pedido (demo)",
                        reference_type="order",
                        reference_id=o.id,
                        occurred_at=_at(o.event_date - timedelta(days=1), 15),
                    )
                )
        weeks = (self.today - start).days // 7
        spend: dict[tuple[int, str], Decimal] = {}
        for name, ing in self.ingredients.items():
            if not ing.is_active:
                continue  # se dejó de usar: queda sin stock ni movimientos
            key, pack, price = self.cheapest[name]
            min_q = ing.min_stock_qty or Decimal(pack)
            # Stock final: la mayoría sobre el mínimo, ~12 % bajo el mínimo para que haya avisos.
            target = _q(
                min_q * Decimal(self.rng.choice([0.4, 0.6]) if self.rng.random() < 0.12 else self.rng.uniform(1.2, 3.5))
            )
            initial = _q(Decimal(pack) * self.rng.randint(1, 3))
            waste_total = _q(consumed[name] * Decimal("0.02"))
            to_buy = consumed[name] + target + waste_total - initial
            self.movements.append(
                StockMovement(
                    pyme_id=pid,
                    created_by=oid,
                    ingredient_id=ing.id,
                    delta_qty=initial,
                    reason=MovementReason.IMPORT,
                    note="Stock inicial (demo)",
                    occurred_at=_at(start, 9),
                )
            )
            balance = initial
            if to_buy > 0:
                packs = int((to_buy / pack).to_integral_value(rounding="ROUND_CEILING"))
                chunks = max(1, min(weeks, packs))
                for i in range(chunks):
                    n = packs // chunks + (1 if i < packs % chunks else 0)
                    if n == 0:
                        continue
                    week = int(i * weeks / chunks)
                    day = start + timedelta(days=week * 7 + self.rng.randint(0, 3))
                    qty = Decimal(n * pack)
                    balance += qty
                    self.movements.append(
                        StockMovement(
                            pyme_id=pid,
                            created_by=oid,
                            ingredient_id=ing.id,
                            delta_qty=qty,
                            reason=MovementReason.PURCHASE,
                            note=f"Compra a {SUPPLIERS[key][0]}",
                            occurred_at=_at(day, 10),
                        )
                    )
                    spend[(week, key)] = spend.get((week, key), Decimal(0)) + Decimal(n * price)
            if waste_total > 0:
                self.movements.append(
                    StockMovement(
                        pyme_id=pid,
                        created_by=oid,
                        ingredient_id=ing.id,
                        delta_qty=-waste_total,
                        reason=MovementReason.WASTE,
                        note="Merma de la semana (demo)",
                        occurred_at=_at(self.today - timedelta(days=self.rng.randint(5, 60)), 18),
                    )
                )
            balance = balance - consumed[name] - waste_total
            diff = _q(target - balance)
            if diff != 0 and abs(diff) < balance:
                self.movements.append(
                    StockMovement(
                        pyme_id=pid,
                        created_by=oid,
                        ingredient_id=ing.id,
                        delta_qty=diff,
                        reason=MovementReason.ADJUSTMENT,
                        note="Ajuste por conteo físico (demo)",
                        occurred_at=_at(self.today - timedelta(days=self.rng.randint(1, 4)), 19),
                    )
                )
                balance += diff
            ing.stock_qty = max(balance, Decimal(0))
        self.s.add_all(self.movements)

        for (week, key), amount in spend.items():
            cash.append(
                CashMovement(
                    pyme_id=pid,
                    created_by=oid,
                    kind=CashKind.EXPENSE,
                    amount_clp=amount,
                    category="Compra de insumos",
                    occurred_on=start + timedelta(days=week * 7 + 1),
                    reference_type="supplier",
                    reference_id=self.suppliers[key].id,
                )
            )
        month = date(start.year, start.month, 1)
        while month <= self.today:
            for cat, value in [
                ("Arriendo cocina", 450000),
                ("Sueldos ayudantes", 980000),
                ("Luz y agua", self.rng.randint(65, 95) * 1000),
                ("Gas", self.rng.randint(55, 90) * 1000),
                ("Contador", 60000),
                ("Publicidad en redes", self.rng.choice([0, 25000, 40000])),
            ]:
                if value:
                    cash.append(
                        CashMovement(
                            pyme_id=pid,
                            created_by=oid,
                            kind=CashKind.EXPENSE,
                            amount_clp=Decimal(value),
                            category=cat,
                            occurred_on=month + timedelta(days=4),
                        )
                    )
            month = (month + timedelta(days=32)).replace(day=1)
        self.cash = cash

    # ----------------------------------------------------------------- cotizaciones (servicio real)
    def quotes(self) -> None:
        from app.modules.quotes import service as quotes
        from app.modules.quotes.schemas import QuoteCreate

        pid = self.pyme.id
        self.s.commit()
        db = open_tenant_session(pid, self.owner.id)
        accepted: list[tuple[Order, Quote]] = []
        try:
            for o in self.order_rows:
                if o.status == OrderStatus.DRAFT and self.rng.random() < 0.25:
                    continue  # borradores sin cotizar todavía
                if o.status == OrderStatus.CANCELLED:  # se cotizó antes de que el cliente lo anulara
                    db.execute(update(Order).where(Order.id == o.id).values(status=OrderStatus.DRAFT))
                versions = 2 if self.rng.random() < 0.15 else 1
                quote = None
                for v in range(versions):
                    quote = quotes.create_quote(
                        db, self.owner_cu, o.id, QuoteCreate(use_stock=self.rng.random() < 0.8), self.today
                    )
                    when = o.created_at + timedelta(minutes=self.rng.randint(3, 40) + v * 1440)
                    quote.created_at = quote.updated_at = when
                assert quote is not None  # noqa: S101
                quote.status = {
                    OrderStatus.DELIVERED: QuoteStatus.ACCEPTED,
                    OrderStatus.CONFIRMED: QuoteStatus.ACCEPTED,
                    OrderStatus.CANCELLED: QuoteStatus.REJECTED,
                }.get(o.status, self.rng.choice([QuoteStatus.DRAFT, QuoteStatus.SENT]))
                if o.status == OrderStatus.CANCELLED:
                    db.execute(update(Order).where(Order.id == o.id).values(status=OrderStatus.CANCELLED))
                db.commit()
                if o.status == OrderStatus.DELIVERED:
                    accepted.append((o, quote))
            self.timings = [q for _o, q in accepted]
            for o, q in accepted:
                self.cash.append(
                    CashMovement(
                        pyme_id=pid,
                        created_by=self.owner.id,
                        kind=CashKind.INCOME,
                        amount_clp=q.total_clp,
                        category="Venta de catering",
                        occurred_on=o.event_date or self.today,
                        reference_type="order",
                        reference_id=o.id,
                    )
                )
        finally:
            db.close()
        self.s.add_all(self.cash)
        self.s.commit()

    # ----------------------------------------------------------------- producción (F2)
    def production(self) -> None:
        pid = self.pyme.id
        with_class = {r.name for r in RECIPES if r.vision}
        rows = []
        for o in self.order_rows:
            if o.status != OrderStatus.DELIVERED or o.event_date is None or (self.today - o.event_date).days > 90:
                continue
            for line in o.lines:
                name = next(n for n, r in self.recipes.items() if r.id == line.recipe_id)
                if name not in with_class:
                    continue
                confirmed = int(self._units(line.qty, line.unit))
                detected = confirmed + self.rng.choice([0, 0, 0, -1, -2, 1, -3])
                rows.append(
                    ProductionRecord(
                        pyme_id=pid,
                        created_by=self.users[1].id,
                        recipe_id=line.recipe_id,
                        detected_qty=max(detected, 0),
                        confirmed_qty=confirmed,
                        model_version="rfdetr-nano-demo (SINTÉTICO)",
                        detections={"note": "conteo sintético de demostración"},
                        was_corrected=detected != confirmed,
                        created_at=_at(o.event_date - timedelta(days=1), 17, self.rng.randint(0, 59)),
                    )
                )
        self.s.add_all(rows)
        self.s.commit()

    # ----------------------------------------------------------------- portal de clientes (servicio real)
    def portal(self) -> None:
        from app.modules.portal import service as portal
        from app.modules.portal.schemas import RequestCreate
        from app.modules.quotes import service as quotes
        from app.modules.quotes.schemas import OrderLineIn

        pid = self.pyme.id
        finals = [r.name for r in RECIPES if r.final]
        plan = ["customer_draft"] * 4 + ["requested"] * 5 + ["accepted"] * 4 + ["rejected"] * 2 + ["cancelled"]
        for i, outcome in enumerate(plan):
            c = self.customers[i % len(self.customers)]
            cu = CurrentUser(c.id, pid, Role.CUSTOMER, c.email, c.full_name)
            db = get_sessionmaker()()  # el portal usa una sesión sin tenant y escribe en la de la pyme elegida
            try:
                lines = [
                    OrderLineIn(recipe_id=self.recipes[p].id, qty=q, unit=u)
                    for p in self.rng.sample(finals, self.rng.randint(1, 3))
                    for q, u in [self._line_for(p)]
                ]
                data = RequestCreate(
                    pyme_id=pid,
                    event_date=self.today + timedelta(days=self.rng.randint(5, 45)),
                    guests=self.rng.choice([20, 30, 50, 80]),
                    lines=lines,
                    notes=self.rng.choice(
                        [None, "Es para un cumpleaños sorpresa (SINTÉTICO)", "¿Pueden despachar a Labranza?"]
                    ),
                )
                order_id = portal.create_request(db, cu, data, self.today)
                if outcome == "cancelled":
                    portal.send_request(db, cu, order_id)
                    portal.cancel_request(db, cu, order_id)
                elif outcome != "customer_draft":
                    portal.send_request(db, cu, order_id)
            finally:
                db.close()
            if outcome in ("accepted", "rejected"):
                staff = open_tenant_session(pid, self.owner.id)
                try:
                    msg = (
                        "¡Confirmado! Les escribimos para el abono (SINTÉTICO)."
                        if outcome == "accepted"
                        else "Esa fecha ya está tomada, lo sentimos (SINTÉTICO)."
                    )
                    quotes.decide_request(staff, order_id, outcome == "accepted", msg)
                finally:
                    staff.close()

    # ----------------------------------------------------------------- documentos, fichas y asistente
    def rag_and_assistant(self) -> None:
        from app.modules.assistant import service as assistant
        from app.modules.assistant.schemas import AskIn
        from app.modules.documents import service as documents
        from app.modules.knowledge import service as knowledge

        pid = self.pyme.id
        emb = get_embeddings()
        db = open_tenant_session(pid, self.owner.id)
        try:
            for path in sorted(DOCS_DIR.iterdir()):
                documents.upload(db, emb, path.name, path.read_bytes())
            knowledge.sync(db, emb)
            llm = get_llm()
            for q in ASSISTANT_QUESTIONS:
                assistant.ask(db, self.owner_cu, AskIn(question=q), llm, emb, self.today)
            rows = list(db.scalars(select(AssistantInteraction).order_by(AssistantInteraction.created_at)))
            for i, row in enumerate(rows):
                row.created_at = _at(
                    self.today - timedelta(days=len(rows) - i), self.rng.randint(9, 20), self.rng.randint(0, 59)
                )
                row.feedback = self.rng.choice([None, None, 1, 1, -1])
            db.commit()
        finally:
            db.close()

    # ----------------------------------------------------------------- métricas, sesiones e intentos
    def metrics_and_auth(self) -> None:
        from app.modules.auth import service as auth

        pid = self.pyme.id
        events: list[MetricEvent] = []
        for q in self.rng.sample(self.timings, min(70, len(self.timings))):
            secs = self.rng.uniform(80, 420)
            events.append(
                MetricEvent(
                    pyme_id=pid,
                    user_id=self.owner.id,
                    kind=MetricKind.QUOTE_TIMING,
                    value_num=_q(secs),
                    payload={
                        "quote_id": str(q.id),
                        "order_id": str(q.order_id),
                        "measured_by": "pwa",
                        "source": "form",
                        "synthetic": True,
                    },
                    created_at=q.created_at,
                )
            )
        for i in range(45):
            events.append(
                MetricEvent(
                    pyme_id=pid,
                    user_id=self.rng.choice(self.users).id,
                    kind=MetricKind.SURVEY,
                    value_num=Decimal(self.rng.choice([3, 4, 4, 5, 5, 5])),
                    payload={
                        "context": self.rng.choice(["general", "quote", "assistant", "vision"]),
                        "synthetic": True,
                        **({"comment": c} if (c := self.rng.choice(SURVEY_COMMENTS)) else {}),
                    },
                    created_at=_at(self.today - timedelta(days=i * 4 + 1), 19),
                )
            )
        for i, (task, ref, secs) in enumerate(
            [
                ("quote", "pedido de referencia P1", 1980),
                ("quote", "pedido de referencia P2", 2460),
                ("quote", "pedido de referencia P3", 1720),
                ("data_lookup", "stock de harina", 140),
                ("data_lookup", "precio de la crema", 95),
                ("data_lookup", "pedidos de la semana", 210),
            ]
        ):
            day = self.today - timedelta(days=200 - i)
            events.append(
                MetricEvent(
                    pyme_id=pid,
                    user_id=self.owner.id,
                    kind=MetricKind.MANUAL_BASELINE,
                    value_num=Decimal(secs),
                    payload={
                        "task": task,
                        "reference": ref,
                        "repetition": 1,
                        "measured_on": day.isoformat(),
                        "tool": "cuaderno y Excel",
                        "synthetic": True,
                    },
                    created_at=_at(day, 11),
                )
            )
        self.s.add_all(events)
        self.s.add_all(
            LoginAttempt(email=OWNER_EMAIL, ip=f"203.0.113.{n}") for n in (10, 11, 12)
        )  # IP de documentación
        auth.issue_refresh_token(self.s, self.owner)  # una sesión abierta (el token en claro no se guarda)
        self.s.commit()


def build(session: Session, today: date | None = None) -> uuid.UUID | None:
    """Crea la pyme grande de demo si no existe. Devuelve su id, o None si ya estaba."""
    today = today or date.today()  # noqa: DTZ011 - fecha local del servidor
    if session.scalar(select(Pyme.id).where(Pyme.name == PYME_NAME, Pyme.is_demo.is_(True))):
        return None
    password_hash = hash_password(os.environ.get(DEMO_PASSWORD_ENV, DEFAULT_DEMO_PASSWORD))
    b = Builder(session, today)
    steps: list[tuple[str, Callable[[], None]]] = [
        ("pyme, usuarias y clientes", lambda: b.base(password_hash)),
        ("insumos, proveedores, precios y recetas", b.catalog),
        ("pedidos", b.orders),
        ("movimientos de stock y caja", b.stock_and_cash),
        ("cotizaciones", b.quotes),
        ("producción", b.production),
        ("portal de clientes", b.portal),
        ("documentos, fichas y asistente", b.rag_and_assistant),
        ("métricas y sesiones", b.metrics_and_auth),
    ]
    for label, step in steps:
        logger.info("… %s", label)
        step()
    session.execute(update(Pyme).where(Pyme.id == b.pyme.id).values(updated_at=datetime.now(UTC)))
    session.commit()
    return b.pyme.id


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Las preguntas de demo se responden sin LLM (rápido y determinista), aunque el .env lo tenga encendido.
    os.environ["ASSISTANT_USE_LLM"] = "false"
    get_settings.cache_clear()
    with get_sessionmaker()() as session:
        try:
            created = build(session)
        except Exception:
            # Los pasos confirman por partes: si uno falla, se borra la pyme a medio crear para poder reintentar.
            session.rollback()
            session.execute(delete(Pyme).where(Pyme.name == PYME_NAME, Pyme.is_demo.is_(True)))
            session.commit()
            raise
    if created is None:
        logger.info("La pyme %s ya existía; no se hizo nada.", PYME_NAME)
        return
    logger.info("Listo: %s (datos SINTÉTICOS).", PYME_NAME)
    logger.info("Dueña: %s · colaboradoras: cocina.llaima@demo.local, ventas.llaima@demo.local", OWNER_EMAIL)
    logger.info("Clientes del portal: cliente1.llaima@demo.local … cliente8.llaima@demo.local")
    logger.info(
        "Enlace del portal: #/cliente/llaima-demo-2026 · contraseña: la de %s o la del seed.", DEMO_PASSWORD_ENV
    )


if __name__ == "__main__":
    main()

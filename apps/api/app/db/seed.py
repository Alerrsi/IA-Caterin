"""Datos de demostración SINTÉTICOS (AGENTS.md, sección 10).

Uso: python -m app.db.seed

- Crea dos pymes de demo para probar el aislamiento entre pymes.
- Los nombres, clientes y precios son inventados: NO son precios reales de mercado.
- Es idempotente: si la pyme de demo ya existe, no la vuelve a crear.
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.enums import (
    BaseUnit,
    DataDomain,
    MovementReason,
    OrderSource,
    OrderStatus,
    OrderUnit,
    PriceSourceKind,
    Role,
)
from app.db.models import (
    DataVersion,
    Ingredient,
    IngredientPrice,
    Order,
    OrderLine,
    Pyme,
    Recipe,
    RecipeLine,
    StockMovement,
    Supplier,
    User,
)
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

DEMO_PASSWORD_ENV = "SEED_DEMO_PASSWORD"  # noqa: S105 - nombre de variable, no un secreto
DEFAULT_DEMO_PASSWORD = "caterin-demo-2026"  # noqa: S105 - contraseña pública de las cuentas de demo
PRICE_DATE = date(2026, 11, 2)

G, ML, U = BaseUnit.GRAM, BaseUnit.MILLILITER, BaseUnit.UNIT


@dataclass(frozen=True)
class IngredientSpec:
    name: str
    unit: BaseUnit
    stock: str
    min_stock: str | None = None
    category: str | None = None
    waste_pct: str | None = None


@dataclass(frozen=True)
class PriceSpec:
    ingredient: str
    label: str
    qty: str
    price: int


@dataclass(frozen=True)
class SupplierSpec:
    name: str
    delivery_days: list[int]
    phone: str | None
    prices: list[PriceSpec]


@dataclass(frozen=True)
class RecipeSpec:
    name: str
    yield_qty: str
    yield_unit: BaseUnit
    vision_class: str | None
    lines: list[tuple[str, str]]
    final: bool = True


@dataclass(frozen=True)
class OrderSpec:
    customer: str
    days_from_today: int
    guests: int | None
    status: OrderStatus
    lines: list[tuple[str, str, OrderUnit]]


@dataclass(frozen=True)
class UserSpec:
    email: str
    name: str
    role: Role


@dataclass(frozen=True)
class PymeSpec:
    name: str
    commune: str
    waste: str
    margin: str | None
    users: list[UserSpec]
    ingredients: list[IngredientSpec]
    suppliers: list[SupplierSpec]
    recipes: list[RecipeSpec]
    orders: list[OrderSpec]


AROMOS = PymeSpec(
    name="Cocina Los Aromos (demo)",
    commune="Temuco",
    waste="5",
    margin="40",
    users=[
        UserSpec("duena.aromos@demo.local", "Dueña Demo Aromos", Role.OWNER),
        UserSpec("colaboradora.aromos@demo.local", "Colaboradora Demo Aromos", Role.COLLABORATOR),
    ],
    ingredients=[
        IngredientSpec("Harina sin polvos", G, "18000", "5000", "Abarrotes"),
        IngredientSpec("Carne molida", G, "6000", "2000", "Carnes"),
        IngredientSpec("Cebolla", G, "8000", "3000", "Verduras", "10"),
        IngredientSpec("Huevo", U, "90", "30", "Lácteos y huevos"),
        IngredientSpec("Aceite vegetal", ML, "5000", "2000", "Abarrotes"),
        IngredientSpec("Manteca", G, "2000", "1000", "Abarrotes"),
        IngredientSpec("Sal", G, "3000", None, "Abarrotes"),
        IngredientSpec("Comino", G, "200", None, "Especias"),
        IngredientSpec("Ají de color", G, "300", None, "Especias"),
        IngredientSpec("Aceituna negra", U, "200", "50", "Abarrotes"),
        IngredientSpec("Pasas", G, "500", None, "Abarrotes"),
        IngredientSpec("Queso mantecoso", G, "3000", "1000", "Lácteos y huevos"),
        IngredientSpec("Salmón ahumado", G, "2500", "500", "Pescados"),
        IngredientSpec("Queso crema", G, "2000", "500", "Lácteos y huevos"),
        IngredientSpec("Pan de cóctel", U, "100", "48", "Panadería"),
        IngredientSpec("Eneldo", G, "50", None, "Verduras"),
        IngredientSpec("Pechuga de pollo", G, "4000", "1000", "Carnes", "5"),
        IngredientSpec("Pimentón rojo", G, "1500", None, "Verduras", "15"),
        IngredientSpec("Tomate cherry", U, "150", None, "Verduras"),
        IngredientSpec("Champiñón", G, "1000", None, "Verduras", "5"),
        IngredientSpec("Masa de hojaldre", G, "2000", None, "Panadería"),
        IngredientSpec("Leche", ML, "4000", None, "Lácteos y huevos"),
        IngredientSpec("Crema de leche", ML, "3000", "1000", "Lácteos y huevos"),
        IngredientSpec("Jamón", G, "1000", None, "Carnes"),
        IngredientSpec("Zapallo", G, "3000", None, "Verduras", "20"),
        IngredientSpec("Polvos de hornear", G, "250", None, "Abarrotes"),
        IngredientSpec("Mantequilla", G, "1000", None, "Lácteos y huevos"),
        IngredientSpec("Azúcar", G, "5000", None, "Abarrotes"),
        IngredientSpec("Limón", U, "30", None, "Verduras"),
        IngredientSpec("Palito de brocheta", U, "300", "100", "Desechables"),
        IngredientSpec("Ciboulette", G, "50", None, "Verduras"),
    ],
    suppliers=[
        SupplierSpec(
            "Harinas Cautín (demo)",
            [2, 4],
            "+56 9 0000 0001",
            [
                PriceSpec("Harina sin polvos", "saco 25 kg", "25000", 21000),
                PriceSpec("Harina sin polvos", "bolsa 1 kg", "1000", 1290),
                PriceSpec("Manteca", "paquete 1 kg", "1000", 2990),
                PriceSpec("Polvos de hornear", "tarro 250 g", "250", 1490),
                PriceSpec("Azúcar", "bolsa 1 kg", "1000", 1190),
                PriceSpec("Sal", "bolsa 1 kg", "1000", 590),
            ],
        ),
        SupplierSpec(
            "Distribuidora Ñielol (demo)",
            [2, 4],
            "+56 9 0000 0002",
            [
                PriceSpec("Harina sin polvos", "saco 25 kg", "25000", 22500),
                PriceSpec("Carne molida", "bolsa 1 kg", "1000", 7990),
                PriceSpec("Pechuga de pollo", "bandeja 1 kg", "1000", 6490),
                PriceSpec("Jamón", "paquete 1 kg", "1000", 8990),
                PriceSpec("Queso mantecoso", "barra 1 kg", "1000", 9990),
                PriceSpec("Salmón ahumado", "paquete 500 g", "500", 11990),
                PriceSpec("Queso crema", "pote 1 kg", "1000", 7490),
                PriceSpec("Crema de leche", "caja 1 L", "1000", 3990),
                PriceSpec("Leche", "caja 1 L", "1000", 1090),
                PriceSpec("Mantequilla", "barra 250 g", "250", 2690),
                PriceSpec("Huevo", "bandeja 30 unidades", "30", 6490),
                PriceSpec("Aceite vegetal", "bidón 5 L", "5000", 11990),
                PriceSpec("Masa de hojaldre", "paquete 1 kg", "1000", 4590),
                PriceSpec("Manteca", "paquete 1 kg", "1000", 3190),
            ],
        ),
        SupplierSpec(
            "Verdulería El Huerto (demo)",
            [1, 3, 5],
            None,
            [
                PriceSpec("Cebolla", "malla 1 kg", "1000", 990),
                PriceSpec("Pimentón rojo", "bolsa 1 kg", "1000", 2490),
                PriceSpec("Tomate cherry", "bandeja 30 unidades", "30", 1990),
                PriceSpec("Champiñón", "bandeja 500 g", "500", 2290),
                PriceSpec("Zapallo", "trozo 1 kg", "1000", 890),
                PriceSpec("Limón", "malla 10 unidades", "10", 1990),
                PriceSpec("Ciboulette", "atado 50 g", "50", 790),
                PriceSpec("Aceituna negra", "frasco 100 unidades", "100", 3490),
                PriceSpec("Pasas", "bolsa 500 g", "500", 2490),
                PriceSpec("Comino", "sobre 100 g", "100", 990),
                PriceSpec("Ají de color", "sobre 100 g", "100", 990),
                PriceSpec("Palito de brocheta", "paquete 100 unidades", "100", 1490),
                PriceSpec("Pan de cóctel", "bolsa 48 unidades", "48", 3990),
                # Eneldo queda sin precio a propósito: muestra el aviso de "sin proveedor con precio".
            ],
        ),
    ],
    recipes=[
        RecipeSpec(
            "Empanadas de pino",
            "12",
            U,
            "empanada_pino",
            [
                ("Harina sin polvos", "600"),
                ("Manteca", "120"),
                ("Carne molida", "700"),
                ("Cebolla", "700"),
                ("Huevo", "3"),
                ("Aceituna negra", "12"),
                ("Pasas", "40"),
                ("Comino", "3"),
                ("Ají de color", "5"),
                ("Sal", "10"),
            ],
        ),
        RecipeSpec(
            "Empanadas de queso",
            "12",
            U,
            "empanada_queso",
            [
                ("Harina sin polvos", "600"),
                ("Manteca", "100"),
                ("Queso mantecoso", "600"),
                ("Sal", "8"),
                ("Aceite vegetal", "800"),
            ],
        ),
        RecipeSpec(
            "Canapés de salmón",
            "24",
            U,
            "canape_salmon",
            [("Pan de cóctel", "24"), ("Queso crema", "240"), ("Salmón ahumado", "300"), ("Eneldo", "5")],
        ),
        RecipeSpec(
            "Brochetas de pollo",
            "12",
            U,
            "brocheta_pollo",
            [
                ("Pechuga de pollo", "900"),
                ("Pimentón rojo", "300"),
                ("Champiñón", "240"),
                ("Palito de brocheta", "12"),
                ("Aceite vegetal", "30"),
                ("Sal", "6"),
            ],
        ),
        RecipeSpec(
            "Mini quiches",
            "24",
            U,
            "mini_quiche",
            [
                ("Masa de hojaldre", "600"),
                ("Huevo", "6"),
                ("Crema de leche", "300"),
                ("Jamón", "200"),
                ("Queso mantecoso", "150"),
                ("Sal", "4"),
            ],
        ),
        RecipeSpec(
            "Sopaipillas",
            "12",
            U,
            "sopaipilla",
            [
                ("Harina sin polvos", "500"),
                ("Zapallo", "300"),
                ("Manteca", "60"),
                ("Polvos de hornear", "5"),
                ("Sal", "6"),
                ("Aceite vegetal", "1000"),
            ],
        ),
        RecipeSpec(
            "Tomates cherry rellenos",
            "24",
            U,
            None,
            [("Tomate cherry", "24"), ("Queso crema", "150"), ("Ciboulette", "5")],
        ),
        RecipeSpec(
            "Pie de limón",
            "1",
            U,
            None,
            [
                ("Harina sin polvos", "250"),
                ("Mantequilla", "125"),
                ("Azúcar", "200"),
                ("Huevo", "4"),
                ("Limón", "4"),
                ("Leche", "400"),
            ],
        ),
    ],
    orders=[
        OrderSpec(
            "Cliente demo A (cóctel de oficina)",
            5,
            50,
            OrderStatus.CONFIRMED,
            [("Empanadas de pino", "80", OrderUnit.UNIT), ("Canapés de salmón", "60", OrderUnit.UNIT)],
        ),
        OrderSpec(
            "Cliente demo B (matrimonio)",
            19,
            120,
            OrderStatus.CONFIRMED,
            [
                ("Empanadas de queso", "20", OrderUnit.DOZEN),
                ("Brochetas de pollo", "240", OrderUnit.UNIT),
                ("Mini quiches", "120", OrderUnit.UNIT),
            ],
        ),
        OrderSpec("Cliente demo C (cumpleaños)", 2, None, OrderStatus.DRAFT, [("Sopaipillas", "3", OrderUnit.DOZEN)]),
        OrderSpec(
            "Cliente demo D (reunión)", -7, 20, OrderStatus.DELIVERED, [("Canapés de salmón", "48", OrderUnit.UNIT)]
        ),
        OrderSpec("Cliente demo E (once)", 10, 8, OrderStatus.CANCELLED, [("Pie de limón", "1", OrderUnit.UNIT)]),
    ],
)

LAGO = PymeSpec(
    name="Banquetería del Lago (demo)",
    commune="Villarrica",
    waste="3",
    margin=None,
    users=[UserSpec("duena.lago@demo.local", "Dueña Demo Lago", Role.OWNER)],
    ingredients=[
        IngredientSpec("Harina sin polvos", G, "10000", "3000", "Abarrotes"),
        IngredientSpec("Manteca", G, "1000", None, "Abarrotes"),
        IngredientSpec("Queso mantecoso", G, "2000", None, "Lácteos y huevos"),
        IngredientSpec("Sal", G, "1000", None, "Abarrotes"),
        IngredientSpec("Aceite vegetal", ML, "3000", None, "Abarrotes"),
    ],
    suppliers=[
        SupplierSpec(
            "Almacén Costanera (demo)",
            [3],
            None,
            [
                PriceSpec("Harina sin polvos", "saco 25 kg", "25000", 23000),
                PriceSpec("Queso mantecoso", "barra 1 kg", "1000", 10490),
                PriceSpec("Manteca", "paquete 1 kg", "1000", 2890),
            ],
        )
    ],
    recipes=[
        RecipeSpec(
            "Empanadas de queso",
            "12",
            U,
            "empanada_queso",
            [("Harina sin polvos", "550"), ("Manteca", "90"), ("Queso mantecoso", "650"), ("Sal", "8")],
        )
    ],
    orders=[
        OrderSpec(
            "Cliente demo L (aniversario)", 7, 30, OrderStatus.CONFIRMED, [("Empanadas de queso", "5", OrderUnit.DOZEN)]
        )
    ],
)

DEMO_PYMES = (AROMOS, LAGO)


def _create_pyme(session: Session, spec: PymeSpec, password_hash: str, today: date) -> Pyme:
    pyme = Pyme(
        name=spec.name,
        commune=spec.commune,
        default_waste_pct=Decimal(spec.waste),
        default_margin_pct=Decimal(spec.margin) if spec.margin else None,
        quote_validity_days=15,
        is_demo=True,
    )
    session.add(pyme)
    session.flush()
    pid = pyme.id

    users = [
        User(pyme_id=pid, email=u.email, full_name=u.name, password_hash=password_hash, role=u.role) for u in spec.users
    ]
    session.add_all(users)
    session.flush()
    owner_id = users[0].id

    ingredients: dict[str, Ingredient] = {}
    for i in spec.ingredients:
        ing = Ingredient(
            pyme_id=pid,
            created_by=owner_id,
            name=i.name,
            base_unit=i.unit,
            stock_qty=Decimal(i.stock),
            min_stock_qty=Decimal(i.min_stock) if i.min_stock else None,
            category=i.category,
            waste_pct=Decimal(i.waste_pct) if i.waste_pct else None,
        )
        ingredients[i.name] = ing
    session.add_all(ingredients.values())
    session.flush()
    session.add_all(
        StockMovement(
            pyme_id=pid,
            created_by=owner_id,
            ingredient_id=ing.id,
            delta_qty=ing.stock_qty,
            reason=MovementReason.IMPORT,
            note="Stock inicial de demo",
        )
        for ing in ingredients.values()
    )

    for s in spec.suppliers:
        supplier = Supplier(pyme_id=pid, created_by=owner_id, name=s.name, delivery_days=s.delivery_days, phone=s.phone)
        session.add(supplier)
        session.flush()
        session.add_all(
            IngredientPrice(
                pyme_id=pid,
                created_by=owner_id,
                ingredient_id=ingredients[p.ingredient].id,
                supplier_id=supplier.id,
                package_label=p.label,
                package_qty=Decimal(p.qty),
                price_clp=Decimal(p.price),
                includes_vat=True,
                price_date=PRICE_DATE,
                source=PriceSourceKind.MANUAL,
            )
            for p in s.prices
        )

    recipes: dict[str, Recipe] = {}
    for r in spec.recipes:
        recipe = Recipe(
            pyme_id=pid,
            created_by=owner_id,
            name=r.name,
            yield_qty=Decimal(r.yield_qty),
            yield_unit=r.yield_unit,
            vision_class=r.vision_class,
            is_final_product=r.final,
        )
        recipe.lines = [
            RecipeLine(pyme_id=pid, created_by=owner_id, ingredient_id=ingredients[name].id, qty=Decimal(qty))
            for name, qty in r.lines
        ]
        recipes[r.name] = recipe
        session.add(recipe)
    session.flush()

    for o in spec.orders:
        order = Order(
            pyme_id=pid,
            created_by=owner_id,
            customer_name=o.customer,
            event_date=today + timedelta(days=o.days_from_today),
            guests=o.guests,
            status=o.status,
            source=OrderSource.FORM,
        )
        order.lines = [
            OrderLine(
                pyme_id=pid,
                created_by=owner_id,
                recipe_id=recipes[name].id,
                position=pos,
                requested_name=name,
                qty=Decimal(qty),
                unit=unit,
            )
            for pos, (name, qty, unit) in enumerate(o.lines)
        ]
        session.add(order)

    session.add_all(DataVersion(pyme_id=pid, domain=d, version=0) for d in DataDomain)
    return pyme


def seed(session: Session, today: date | None = None) -> list[uuid.UUID]:
    """Crea las pymes de demo que falten. Devuelve los ids de las pymes creadas."""
    today = today or date.today()  # noqa: DTZ011 - fecha local del servidor para los pedidos de demo
    password_hash = hash_password(os.environ.get(DEMO_PASSWORD_ENV, DEFAULT_DEMO_PASSWORD))
    created: list[uuid.UUID] = []
    for spec in DEMO_PYMES:
        exists = session.scalar(select(Pyme.id).where(Pyme.name == spec.name, Pyme.is_demo.is_(True)))
        if exists:
            continue
        created.append(_create_pyme(session, spec, password_hash, today).id)
    session.commit()
    return created


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with get_sessionmaker()() as session:
        created = seed(session)
    if created:
        logger.info("Pymes de demo creadas: %d (datos sintéticos).", len(created))
        logger.info("Usuarias: duena.aromos@demo.local, colaboradora.aromos@demo.local, duena.lago@demo.local")
        logger.info("Contraseña de demo: la de %s o la predeterminada del seed.", DEMO_PASSWORD_ENV)
    else:
        logger.info("Las pymes de demo ya existían; no se hizo nada.")


if __name__ == "__main__":
    main()

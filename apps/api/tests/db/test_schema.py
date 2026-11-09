import uuid
from decimal import Decimal

import pytest
from alembic import command
from alembic.util.exc import CommandError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import BaseUnit, PriceSourceKind
from app.db.models import Ingredient, IngredientPrice, Pyme, Recipe, RecipeLine, StockMovement, Supplier, User
from app.db.seed import seed
from tests.conftest import alembic_config


def _pyme(db: Session, name: str) -> Pyme:
    p = Pyme(name=name)
    db.add(p)
    db.flush()
    return p


def test_migrations_down_and_up(migrated_db: None) -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    command.check(cfg)  # modelos y migraciones coinciden


def test_alembic_check_detects_no_drift(migrated_db: None) -> None:
    try:
        command.check(alembic_config())
    except CommandError as exc:  # pragma: no cover - solo si hay drift
        pytest.fail(f"Los modelos y las migraciones no coinciden: {exc}")


def test_cross_tenant_reference_is_rejected_by_database(db: Session) -> None:
    a, b = _pyme(db, "A"), _pyme(db, "B")
    ing_b = Ingredient(pyme_id=b.id, name="Harina", base_unit=BaseUnit.GRAM)
    recipe_a = Recipe(pyme_id=a.id, name="Empanadas", yield_qty=Decimal(12), yield_unit=BaseUnit.UNIT)
    db.add_all([ing_b, recipe_a])
    db.flush()
    db.add(RecipeLine(pyme_id=a.id, recipe_id=recipe_a.id, ingredient_id=ing_b.id, qty=Decimal(100)))
    with pytest.raises(IntegrityError, match="fk_recipe_line_ingredient_id_ingredient"):
        db.flush()


def test_names_unique_per_pyme_case_insensitive(db: Session) -> None:
    a, b = _pyme(db, "A"), _pyme(db, "B")
    db.add_all(
        [
            Ingredient(pyme_id=a.id, name="Harina", base_unit=BaseUnit.GRAM),
            Ingredient(pyme_id=b.id, name="Harina", base_unit=BaseUnit.GRAM),  # otra pyme: permitido
        ]
    )
    db.flush()
    db.add(Ingredient(pyme_id=a.id, name="HARINA", base_unit=BaseUnit.GRAM))
    with pytest.raises(IntegrityError, match="uq_ingredient_pyme_name"):
        db.flush()


def test_only_one_current_price_per_package(db: Session) -> None:
    from datetime import date

    a = _pyme(db, "A")
    ing = Ingredient(pyme_id=a.id, name="Harina", base_unit=BaseUnit.GRAM)
    sup = Supplier(pyme_id=a.id, name="Molino")
    db.add_all([ing, sup])
    db.flush()

    def price(current: bool) -> IngredientPrice:
        return IngredientPrice(
            pyme_id=a.id,
            ingredient_id=ing.id,
            supplier_id=sup.id,
            package_label="saco 25 kg",
            package_qty=Decimal(25000),
            price_clp=Decimal(21000),
            price_date=date(2026, 11, 1),
            source=PriceSourceKind.MANUAL,
            is_current=current,
        )

    db.add_all([price(False), price(True)])  # versiones antiguas no chocan
    db.flush()
    db.add(price(True))
    with pytest.raises(IntegrityError, match="uq_ingredient_price_current"):
        db.flush()


def test_check_constraints(db: Session) -> None:
    a = _pyme(db, "A")
    db.add(Recipe(pyme_id=a.id, name="Mala", yield_qty=Decimal(0), yield_unit=BaseUnit.UNIT))
    with pytest.raises(IntegrityError, match="yield_positive"):
        db.flush()


def test_seed_is_idempotent_and_consistent(db: Session) -> None:
    first = seed(db)
    second = seed(db)
    assert len(first) == 2
    assert second == []
    assert db.scalar(select(func.count()).select_from(Pyme)) == 2
    assert db.scalar(select(func.count()).select_from(User)) == 3
    # el saldo cacheado coincide con la suma del libro de movimientos
    for ing in db.scalars(select(Ingredient)):
        total = db.scalar(select(func.sum(StockMovement.delta_qty)).where(StockMovement.ingredient_id == ing.id))
        assert total == ing.stock_qty
    # todas las pymes del seed están marcadas como demo
    assert all(p.is_demo for p in db.scalars(select(Pyme)))
    assert uuid.UUID(str(first[0]))

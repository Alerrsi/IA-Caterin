"""La pyme grande de demo (`app.db.demo_full`) se puede crear de punta a punta y llena todas las tablas.

Usa embeddings y LLM falsos: lo que se prueba es que el poblador siga funcionando cuando cambie el código.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embeddings import FakeEmbeddings
from app.core.llm import FakeProvider
from app.db import demo_full
from app.db.base import Base
from app.db.models import Ingredient, Pyme, Recipe, StockMovement


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()  # que las demás pruebas no hereden ASSISTANT_USE_LLM=false


def test_demo_full_fills_every_table(
    db: Session, monkeypatch: pytest.MonkeyPatch, fresh_settings: None, tmp_path: Path
) -> None:
    monkeypatch.setattr(demo_full, "get_embeddings", FakeEmbeddings)
    monkeypatch.setattr(demo_full, "get_llm", FakeProvider)
    monkeypatch.setenv("ASSISTANT_USE_LLM", "false")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    pyme_id = demo_full.build(db, today=date(2026, 11, 10))
    assert pyme_id is not None
    assert demo_full.build(db, today=date(2026, 11, 10)) is None  # idempotente

    empty = []
    for table in Base.metadata.sorted_tables:
        if db.scalar(select(func.count()).select_from(table)) == 0:
            empty.append(table.name)
    assert empty == []

    pyme = db.get(Pyme, pyme_id)
    assert pyme is not None and pyme.is_demo and pyme.customer_code == "llaima-demo-2026"
    # Catálogo del portal (ADR-009): logo guardado, descripción y productos con categoría.
    assert pyme.description and pyme.logo_path and (tmp_path / pyme.logo_path).is_file()
    categories = db.scalars(select(Recipe.category).where(Recipe.pyme_id == pyme_id, Recipe.is_final_product))
    assert all(categories)
    # El stock de cada insumo es la suma de su libro de movimientos (ADR-004) y nunca negativo.
    ledger = dict(
        db.execute(
            select(StockMovement.ingredient_id, func.sum(StockMovement.delta_qty))
            .where(StockMovement.pyme_id == pyme_id)
            .group_by(StockMovement.ingredient_id)
        ).all()
    )
    for ing in db.scalars(select(Ingredient).where(Ingredient.pyme_id == pyme_id, Ingredient.is_active)):
        assert ing.stock_qty >= 0
        assert abs(ing.stock_qty - ledger.get(ing.id, 0)) < 0.01, ing.name
    incomplete = db.scalar(text("SELECT count(*) FROM quote WHERE pyme_id = :p AND NOT is_complete"), {"p": pyme_id})
    assert incomplete == 0

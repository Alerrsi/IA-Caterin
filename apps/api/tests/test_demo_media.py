"""T21: fotos de producto de la pyme de demo (`app.db.demo_media`)."""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import demo_full
from app.db.demo_media import PHOTOS_DIR, assign_demo_photos, photo_for, slugify
from app.db.enums import BaseUnit
from app.db.models import Pyme, Recipe


def test_slugify_matches_photo_names() -> None:
    assert slugify("Sándwich de ave mayo") == "sandwich-de-ave-mayo"
    assert slugify("Canapés de queso de cabra y murta") == "canapes-de-queso-de-cabra-y-murta"
    assert slugify("  Empanadas de camarón queso ") == "empanadas-de-camaron-queso"
    assert photo_for("Empanadas de pino") is not None
    assert photo_for("Mote con huesillo") is None  # sin foto libre razonable: queda sin foto


def test_every_demo_photo_belongs_to_a_demo_recipe() -> None:
    """Una foto con un nombre mal escrito nunca se asignaría: se detecta aquí."""
    recipes = {slugify(r.name) for r in demo_full.RECIPES}
    photos = {p.stem for p in PHOTOS_DIR.glob("*.webp")}
    assert photos, "no hay fotos de demo"
    assert photos <= recipes, photos - recipes
    assert all(p.stat().st_size < 80 * 1024 for p in PHOTOS_DIR.glob("*.webp"))


def _pyme(db: Session, name: str, recipes: dict[str, str | None]) -> Pyme:
    pyme = Pyme(name=name)
    db.add(pyme)
    db.flush()
    for recipe_name, photo in recipes.items():
        db.add(
            Recipe(
                pyme_id=pyme.id,
                name=recipe_name,
                yield_qty=Decimal(12),
                yield_unit=BaseUnit.UNIT,
                photo_path=photo,
            )
        )
    db.commit()
    return pyme


def test_assign_is_idempotent_keeps_existing_photos_and_isolates_pymes(
    db: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(get_settings(), "storage_dir", tmp_path)
    mine = _pyme(
        db,
        "Pyme con demo",
        {"Empanadas de pino": None, "Sopaipillas": None, "Alfajores": "media/propia.webp", "Receta inventada": None},
    )
    other = _pyme(db, "Otra pyme", {"Empanadas de pino": None})

    assert assign_demo_photos(db, mine.id) == 2  # pino y sopaipillas; alfajores ya tenía la suya
    rows = dict(db.execute(select(Recipe.name, Recipe.photo_path).where(Recipe.pyme_id == mine.id)).all())
    assert rows["Alfajores"] == "media/propia.webp"  # no pisa la foto que subió la usuaria
    assert rows["Receta inventada"] is None
    for name in ("Empanadas de pino", "Sopaipillas"):
        path = rows[name]
        assert path is not None and path.startswith(f"media/{mine.id}/")
        assert (tmp_path / path).is_file()

    assert assign_demo_photos(db, mine.id) == 0  # idempotente
    again = dict(db.execute(select(Recipe.name, Recipe.photo_path).where(Recipe.pyme_id == mine.id)).all())
    assert again == rows

    other_photo = db.scalar(select(Recipe.photo_path).where(Recipe.pyme_id == other.id))
    assert other_photo is None  # la otra pyme no se toca

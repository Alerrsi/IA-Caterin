"""Fotos de producto de la pyme de demo (T21). Fotos de licencia libre: ver THIRD_PARTY_NOTICES.md.

Las fotos viven en `app/db/demo_photos/<slug>.webp`, donde `slug` sale del nombre de la receta ("Sándwich de ave
mayo" -> `sandwich-de-ave-mayo`). `assign_demo_photos` las guarda como cualquier foto subida (`core.media`:
`storage_dir/media/<pyme_id>/<sha256>.webp`) y las asigna **solo a recetas sin foto**, así que se puede correr las
veces que sea sin pisar una foto que la usuaria haya subido.

Uso sobre una base existente (no borra nada): `python -m app.db.demo_media`.
"""

import logging
import re
import unicodedata
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import media
from app.db.models import Pyme, Recipe

logger = logging.getLogger(__name__)

PHOTOS_DIR = Path(__file__).parent / "demo_photos"


def slugify(name: str) -> str:
    """Slug del nombre de la receta: «Canapés de ave palta» -> `canapes-de-ave-palta`."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def photo_for(name: str) -> Path | None:
    path = PHOTOS_DIR / f"{slugify(name)}.webp"
    return path if path.is_file() else None


def assign_demo_photos(session: Session, pyme_id: uuid.UUID) -> int:
    """Pone foto a las recetas de la pyme que no tienen y que tienen foto de demo. Devuelve cuántas asignó."""
    recipes = session.scalars(
        select(Recipe).where(Recipe.pyme_id == pyme_id, Recipe.photo_path.is_(None)).order_by(Recipe.name)
    ).all()
    assigned = 0
    for recipe in recipes:
        path = photo_for(recipe.name)
        if path is None:
            continue
        recipe.photo_path = media.save_image(pyme_id, path.read_bytes(), media.Kind.PHOTO)
        assigned += 1
    session.commit()
    return assigned


def main() -> None:  # pragma: no cover - comando de consola
    from app.db.demo_full import PYME_NAME
    from app.db.session import get_sessionmaker

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with get_sessionmaker()() as session:
        pyme_id = session.scalar(select(Pyme.id).where(Pyme.name == PYME_NAME, Pyme.is_demo.is_(True)))
        if pyme_id is None:
            logger.info("No existe la pyme de demo «%s»: créala con `python -m app.db.demo_full`.", PYME_NAME)
            return
        logger.info("Fotos asignadas a %d productos de «%s».", assign_demo_photos(session, pyme_id), PYME_NAME)


if __name__ == "__main__":  # pragma: no cover
    main()

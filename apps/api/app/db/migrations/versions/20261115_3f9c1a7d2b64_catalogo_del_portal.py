"""catálogo del portal (ADR-009): logo y descripción de la pyme; foto, descripción, categoría y visibilidad del producto

Todo es opcional y `visible_in_catalog` vale `true` por defecto, así el cliente sigue viendo lo mismo que antes.
Las imágenes viven en `storage_dir/media/<pyme_id>/`; la tabla guarda solo la ruta relativa.

Revision ID: 3f9c1a7d2b64
Revises: 7cd8acbbfff0
Create Date: 2026-11-15 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f9c1a7d2b64"
down_revision: str | None = "7cd8acbbfff0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pyme", sa.Column("description", sa.String(280), nullable=True))
    op.add_column("pyme", sa.Column("logo_path", sa.String(200), nullable=True))
    op.add_column("recipe", sa.Column("catalog_description", sa.String(500), nullable=True))
    op.add_column("recipe", sa.Column("category", sa.String(60), nullable=True))
    op.add_column("recipe", sa.Column("photo_path", sa.String(200), nullable=True))
    op.add_column(
        "recipe", sa.Column("visible_in_catalog", sa.Boolean(), server_default=sa.text("true"), nullable=False)
    )


def downgrade() -> None:
    # Los archivos de imagen quedan en el disco; bajar la migración solo olvida sus rutas.
    op.drop_column("recipe", "visible_in_catalog")
    op.drop_column("recipe", "photo_path")
    op.drop_column("recipe", "category")
    op.drop_column("recipe", "catalog_description")
    op.drop_column("pyme", "logo_path")
    op.drop_column("pyme", "description")

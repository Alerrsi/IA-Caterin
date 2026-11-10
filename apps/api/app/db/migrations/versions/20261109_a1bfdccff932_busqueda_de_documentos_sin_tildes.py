"""documentos: búsqueda de texto completo sin tildes (unaccent)

Quien escribe "minimo" desde el celular debe encontrar "mínimo" en el documento: el stemmer 'spanish' de
Postgres no quita tildes, así que el texto y la consulta se pasan por unaccent. Postgres 16 no permite cambiar
la expresión de una columna generada: se borra y se vuelve a crear (los fragmentos se recalculan solos).

Revision ID: a1bfdccff932
Revises: c4a7e2d91b30
Create Date: 2026-11-09 23:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1bfdccff932"
down_revision: str | None = "c4a7e2d91b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tsv(expression: str) -> None:
    op.drop_index("ix_document_chunk_tsv", table_name="document_chunk", postgresql_using="gin")
    op.drop_column("document_chunk", "tsv")
    op.add_column(
        "document_chunk",
        sa.Column("tsv", postgresql.TSVECTOR(), sa.Computed(expression, persisted=True), nullable=False),
    )
    op.create_index("ix_document_chunk_tsv", "document_chunk", ["tsv"], unique=False, postgresql_using="gin")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # unaccent() es STABLE; una columna generada exige una función IMMUTABLE con el diccionario explícito.
    op.execute(
        "CREATE OR REPLACE FUNCTION caterin_unaccent(text) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT "
        "AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$"
    )
    _tsv("to_tsvector('spanish', caterin_unaccent(text))")


def downgrade() -> None:
    _tsv("to_tsvector('spanish', text)")
    op.execute("DROP FUNCTION IF EXISTS caterin_unaccent(text)")

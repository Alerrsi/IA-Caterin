"""fichas del negocio para RAG (ADR-006): knowledge_card y knowledge_sync

Las fichas se generan desde las tablas de negocio; no son fuente de verdad. Bajar la migración las borra sin
perder datos del negocio.

Revision ID: 67b617a7b8cb
Revises: a1bfdccff932
Create Date: 2026-11-10 06:22:49.712587
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "67b617a7b8cb"
down_revision: str | None = "a1bfdccff932"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_card",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('spanish', caterin_unaccent(text))", persisted=True),
            nullable=False,
        ),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column("embedding_model", sa.String(length=80), nullable=False),
        sa.Column("embedding_version", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('ingredient', 'recipe', 'supplier', 'order')", name=op.f("ck_knowledge_card_kind_valid")
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_knowledge_card_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_knowledge_card_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_card")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_knowledge_card_pyme_id_id"),
        sa.UniqueConstraint("pyme_id", "kind", "entity_id", name="uq_knowledge_card_entity"),
    )
    op.create_index(
        "ix_knowledge_card_embedding",
        "knowledge_card",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(op.f("ix_knowledge_card_pyme_id"), "knowledge_card", ["pyme_id"], unique=False)
    op.create_index("ix_knowledge_card_tsv", "knowledge_card", ["tsv"], unique=False, postgresql_using="gin")
    op.create_table(
        "knowledge_sync",
        sa.Column(
            "domain",
            sa.Enum(
                "inventory",
                "recipes",
                "suppliers",
                "orders",
                "cash",
                "documents",
                "production",
                name="knowledge_sync_domain",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_knowledge_sync_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_knowledge_sync_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_sync")),
        sa.UniqueConstraint("pyme_id", "domain", name="uq_knowledge_sync_domain"),
        sa.UniqueConstraint("pyme_id", "id", name="uq_knowledge_sync_pyme_id_id"),
    )
    op.create_index(op.f("ix_knowledge_sync_pyme_id"), "knowledge_sync", ["pyme_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_sync_pyme_id"), table_name="knowledge_sync")
    op.drop_table("knowledge_sync")
    op.drop_index("ix_knowledge_card_tsv", table_name="knowledge_card", postgresql_using="gin")
    op.drop_index(op.f("ix_knowledge_card_pyme_id"), table_name="knowledge_card")
    op.drop_index(
        "ix_knowledge_card_embedding",
        table_name="knowledge_card",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("knowledge_card")

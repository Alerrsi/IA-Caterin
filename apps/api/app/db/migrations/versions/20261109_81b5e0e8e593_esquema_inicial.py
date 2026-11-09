"""esquema inicial

Revision ID: 81b5e0e8e593
Revises:
Create Date: 2026-11-09 20:11:06.674864
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "81b5e0e8e593"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extensiones: pgvector (embeddings) y citext (correos sin distinguir mayúsculas).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table(
        "login_attempt",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempt")),
    )
    op.create_index(op.f("ix_login_attempt_created_at"), "login_attempt", ["created_at"], unique=False)
    op.create_index(op.f("ix_login_attempt_email"), "login_attempt", ["email"], unique=False)
    op.create_index(op.f("ix_login_attempt_ip"), "login_attempt", ["ip"], unique=False)
    op.create_table(
        "pyme",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("rut", sa.String(length=12), nullable=True),
        sa.Column("commune", sa.String(length=80), nullable=True),
        sa.Column("default_waste_pct", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False),
        sa.Column("default_margin_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("vat_pct", sa.Numeric(precision=5, scale=2), server_default="19.00", nullable=False),
        sa.Column("prices_include_vat", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("quote_validity_days", sa.SmallInteger(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "default_margin_pct IS NULL OR default_margin_pct >= 0", name=op.f("ck_pyme_margin_positive")
        ),
        sa.CheckConstraint("default_waste_pct >= 0 AND default_waste_pct < 100", name=op.f("ck_pyme_waste_range")),
        sa.CheckConstraint("vat_pct >= 0 AND vat_pct < 100", name=op.f("ck_pyme_vat_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pyme")),
    )
    op.create_table(
        "app_user",
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "collaborator", name="role", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_app_user_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_app_user_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_app_user_pyme_id_id"),
    )
    op.create_index(op.f("ix_app_user_pyme_id"), "app_user", ["pyme_id"], unique=False)
    op.create_table(
        "data_version",
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column(
            "domain",
            sa.Enum(
                "inventory",
                "recipes",
                "suppliers",
                "orders",
                "cash",
                "documents",
                name="data_domain",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.BigInteger(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_data_version_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("pyme_id", "domain", name=op.f("pk_data_version")),
    )
    op.create_table(
        "assistant_interaction",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("intent", sa.String(length=60), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("router_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "entities", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "queries", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "sources", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fallback_reason", sa.String(length=40), nullable=True),
        sa.Column("llm_model", sa.String(length=60), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("first_token_ms", sa.Integer(), nullable=True),
        sa.Column("intents_version", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_assistant_interaction_created_by_app_user",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "user_id"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_assistant_interaction_user_id_app_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_assistant_interaction_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_interaction")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_assistant_interaction_pyme_id_id"),
    )
    op.create_index(op.f("ix_assistant_interaction_pyme_id"), "assistant_interaction", ["pyme_id"], unique=False)
    op.create_table(
        "cash_movement",
        sa.Column(
            "kind",
            sa.Enum("income", "expense", name="cash_kind", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("amount_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("reference_type", sa.String(length=40), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount_clp > 0", name=op.f("ck_cash_movement_amount_positive")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_cash_movement_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_cash_movement_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cash_movement")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_cash_movement_pyme_id_id"),
    )
    op.create_index(op.f("ix_cash_movement_pyme_id"), "cash_movement", ["pyme_id"], unique=False)
    op.create_table(
        "catering_order",
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("customer_contact", sa.String(length=120), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("guests", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "confirmed",
                "delivered",
                "cancelled",
                name="order_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("text", "list", "form", name="order_source", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extraction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("guests IS NULL OR guests > 0", name=op.f("ck_catering_order_guests_positive")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_catering_order_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_catering_order_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catering_order")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_catering_order_pyme_id_id"),
    )
    op.create_index("ix_catering_order_pyme_event", "catering_order", ["pyme_id", "event_date"], unique=False)
    op.create_index(op.f("ix_catering_order_pyme_id"), "catering_order", ["pyme_id"], unique=False)
    op.create_table(
        "document",
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=255), nullable=False),
        sa.Column(
            "index_status",
            sa.Enum(
                "pending",
                "indexed",
                "failed",
                name="index_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_document_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_document_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_document_pyme_id_id"),
        sa.UniqueConstraint("pyme_id", "sha256", name="uq_document_pyme_sha256"),
    )
    op.create_index(op.f("ix_document_pyme_id"), "document", ["pyme_id"], unique=False)
    op.create_table(
        "ingredient",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "base_unit",
            sa.Enum("g", "ml", "unit", name="base_unit", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("stock_qty", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False),
        sa.Column("min_stock_qty", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("waste_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("density_g_per_ml", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "density_g_per_ml IS NULL OR density_g_per_ml > 0", name=op.f("ck_ingredient_density_positive")
        ),
        sa.CheckConstraint(
            "waste_pct IS NULL OR (waste_pct >= 0 AND waste_pct < 100)", name=op.f("ck_ingredient_waste_range")
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_ingredient_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_ingredient_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingredient")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_ingredient_pyme_id_id"),
    )
    op.create_index(op.f("ix_ingredient_pyme_id"), "ingredient", ["pyme_id"], unique=False)
    op.create_index("uq_ingredient_pyme_name", "ingredient", ["pyme_id", sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "metric_event",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "survey",
                "quote_timing",
                "assistant_latency",
                "vision_latency",
                "manual_baseline",
                name="metric_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("value_num", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_metric_event_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "user_id"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_metric_event_user_id_app_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_metric_event_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_event")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_metric_event_pyme_id_id"),
    )
    op.create_index(op.f("ix_metric_event_pyme_id"), "metric_event", ["pyme_id"], unique=False)
    op.create_index(
        "ix_metric_event_pyme_kind_created", "metric_event", ["pyme_id", "kind", "created_at"], unique=False
    )
    op.create_table(
        "recipe",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("yield_qty", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column(
            "yield_unit",
            sa.Enum("g", "ml", "unit", name="yield_unit", native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column("is_final_product", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("vision_class", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("yield_qty > 0", name=op.f("ck_recipe_yield_positive")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_recipe_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_recipe_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_recipe_pyme_id_id"),
    )
    op.create_index(op.f("ix_recipe_pyme_id"), "recipe", ["pyme_id"], unique=False)
    op.create_index("uq_recipe_pyme_name", "recipe", ["pyme_id", sa.literal_column("lower(name)")], unique=True)
    op.create_index(
        "uq_recipe_pyme_vision_class",
        "recipe",
        ["pyme_id", "vision_class"],
        unique=True,
        postgresql_where=sa.text("vision_class IS NOT NULL"),
    )
    op.create_table(
        "refresh_token",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_refresh_token_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "user_id"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_refresh_token_user_id_app_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_refresh_token_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_refresh_token_pyme_id_id"),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_token_token_hash")),
    )
    op.create_index(op.f("ix_refresh_token_pyme_id"), "refresh_token", ["pyme_id"], unique=False)
    op.create_table(
        "supplier",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("delivery_days", sa.ARRAY(sa.SmallInteger()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_supplier_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_supplier_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplier")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_supplier_pyme_id_id"),
    )
    op.create_index(op.f("ix_supplier_pyme_id"), "supplier", ["pyme_id"], unique=False)
    op.create_index("uq_supplier_pyme_name", "supplier", ["pyme_id", sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "document_chunk",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "tsv", postgresql.TSVECTOR(), sa.Computed("to_tsvector('spanish', text)", persisted=True), nullable=False
        ),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column("embedding_model", sa.String(length=80), nullable=False),
        sa.Column("embedding_version", sa.String(length=40), nullable=False),
        sa.Column(
            "meta", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_document_chunk_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "document_id"],
            ["document.pyme_id", "document.id"],
            name="fk_document_chunk_document_id_document",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_document_chunk_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunk")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_document_chunk_pyme_id_id"),
    )
    op.create_index(
        "ix_document_chunk_embedding",
        "document_chunk",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(op.f("ix_document_chunk_pyme_id"), "document_chunk", ["pyme_id"], unique=False)
    op.create_index("ix_document_chunk_tsv", "document_chunk", ["tsv"], unique=False, postgresql_using="gin")
    op.create_table(
        "ingredient_price",
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("package_label", sa.String(length=80), nullable=False),
        sa.Column("package_qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("price_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("includes_vat", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "manual",
                "csv",
                "excel",
                "price_list",
                "price_source",
                name="price_source_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("package_qty > 0", name=op.f("ck_ingredient_price_package_qty_positive")),
        sa.CheckConstraint("price_clp >= 0", name=op.f("ck_ingredient_price_price_positive")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_ingredient_price_created_by_app_user",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "ingredient_id"],
            ["ingredient.pyme_id", "ingredient.id"],
            name="fk_ingredient_price_ingredient_id_ingredient",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "supplier_id"],
            ["supplier.pyme_id", "supplier.id"],
            name="fk_ingredient_price_supplier_id_supplier",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_ingredient_price_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingredient_price")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_ingredient_price_pyme_id_id"),
    )
    op.create_index(op.f("ix_ingredient_price_pyme_id"), "ingredient_price", ["pyme_id"], unique=False)
    op.create_index(
        "uq_ingredient_price_current",
        "ingredient_price",
        ["pyme_id", "ingredient_id", "supplier_id", "package_label"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "order_line",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("requested_name", sa.String(length=160), nullable=False),
        sa.Column("qty", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column(
            "unit",
            sa.Enum(
                "unit",
                "dozen",
                "g",
                "kg",
                "ml",
                "l",
                "portion",
                name="order_unit",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty > 0", name=op.f("ck_order_line_qty_positive")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_order_line_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "order_id"],
            ["catering_order.pyme_id", "catering_order.id"],
            name="fk_order_line_order_id_catering_order",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "recipe_id"],
            ["recipe.pyme_id", "recipe.id"],
            name="fk_order_line_recipe_id_recipe",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_order_line_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_line")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_order_line_pyme_id_id"),
    )
    op.create_index(op.f("ix_order_line_pyme_id"), "order_line", ["pyme_id"], unique=False)
    op.create_table(
        "production_record",
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("detected_qty", sa.Integer(), nullable=True),
        sa.Column("confirmed_qty", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("model_version", sa.String(length=60), nullable=True),
        sa.Column("detections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("was_corrected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("client_op_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("confirmed_qty >= 0", name=op.f("ck_production_record_confirmed_positive")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_production_record_created_by_app_user",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "recipe_id"],
            ["recipe.pyme_id", "recipe.id"],
            name="fk_production_record_recipe_id_recipe",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_production_record_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_record")),
        sa.UniqueConstraint("pyme_id", "client_op_id", name="uq_production_record_client_op"),
        sa.UniqueConstraint("pyme_id", "id", name="uq_production_record_pyme_id_id"),
    )
    op.create_index(op.f("ix_production_record_pyme_id"), "production_record", ["pyme_id"], unique=False)
    op.create_table(
        "quote",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "sent",
                "accepted",
                "rejected",
                name="quote_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("price_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ingredients_cost_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("margin_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("net_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("vat_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("total_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("is_complete", sa.Boolean(), nullable=False),
        sa.Column("pdf_path", sa.String(length=255), nullable=True),
        sa.Column("calc_version", sa.String(length=20), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_quote_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "order_id"],
            ["catering_order.pyme_id", "catering_order.id"],
            name="fk_quote_order_id_catering_order",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_quote_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote")),
        sa.UniqueConstraint("order_id", "version", name="uq_quote_order_version"),
        sa.UniqueConstraint("pyme_id", "id", name="uq_quote_pyme_id_id"),
    )
    op.create_index(op.f("ix_quote_pyme_id"), "quote", ["pyme_id"], unique=False)
    op.create_table(
        "recipe_line",
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("waste_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty > 0", name=op.f("ck_recipe_line_qty_positive")),
        sa.CheckConstraint(
            "waste_pct IS NULL OR (waste_pct >= 0 AND waste_pct < 100)", name=op.f("ck_recipe_line_waste_range")
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_recipe_line_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "ingredient_id"],
            ["ingredient.pyme_id", "ingredient.id"],
            name="fk_recipe_line_ingredient_id_ingredient",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "recipe_id"],
            ["recipe.pyme_id", "recipe.id"],
            name="fk_recipe_line_recipe_id_recipe",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_recipe_line_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipe_line")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_recipe_line_pyme_id_id"),
        sa.UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_line_ingredient"),
    )
    op.create_index(op.f("ix_recipe_line_pyme_id"), "recipe_line", ["pyme_id"], unique=False)
    op.create_table(
        "stock_movement",
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("delta_qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "purchase",
                "consumption",
                "adjustment",
                "waste",
                "production",
                "import",
                name="movement_reason",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("reference_type", sa.String(length=40), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("client_op_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_stock_movement_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "ingredient_id"],
            ["ingredient.pyme_id", "ingredient.id"],
            name="fk_stock_movement_ingredient_id_ingredient",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_stock_movement_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movement")),
        sa.UniqueConstraint("pyme_id", "client_op_id", name="uq_stock_movement_client_op"),
        sa.UniqueConstraint("pyme_id", "id", name="uq_stock_movement_pyme_id_id"),
    )
    op.create_index(op.f("ix_stock_movement_pyme_id"), "stock_movement", ["pyme_id"], unique=False)
    op.create_table(
        "quote_line",
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("required_qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("stock_used_qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("to_buy_qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("ingredient_price_id", sa.Uuid(), nullable=True),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("packages_to_buy", sa.Integer(), nullable=False),
        sa.Column("unit_price_clp", sa.Numeric(precision=12, scale=0), nullable=True),
        sa.Column("subtotal_clp", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=True),
        sa.Column(
            "alternatives",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pyme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"], ["app_user.pyme_id", "app_user.id"], name="fk_quote_line_created_by_app_user"
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "ingredient_id"],
            ["ingredient.pyme_id", "ingredient.id"],
            name="fk_quote_line_ingredient_id_ingredient",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "ingredient_price_id"],
            ["ingredient_price.pyme_id", "ingredient_price.id"],
            name="fk_quote_line_ingredient_price_id_ingredient_price",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "quote_id"],
            ["quote.pyme_id", "quote.id"],
            name="fk_quote_line_quote_id_quote",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "supplier_id"],
            ["supplier.pyme_id", "supplier.id"],
            name="fk_quote_line_supplier_id_supplier",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["pyme_id"], ["pyme.id"], name=op.f("fk_quote_line_pyme_id_pyme"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_line")),
        sa.UniqueConstraint("pyme_id", "id", name="uq_quote_line_pyme_id_id"),
    )
    op.create_index(op.f("ix_quote_line_pyme_id"), "quote_line", ["pyme_id"], unique=False)


def downgrade() -> None:
    # Las extensiones no se eliminan: pueden estar en uso por otras bases del mismo servidor.
    op.drop_index(op.f("ix_quote_line_pyme_id"), table_name="quote_line")
    op.drop_table("quote_line")
    op.drop_index(op.f("ix_stock_movement_pyme_id"), table_name="stock_movement")
    op.drop_table("stock_movement")
    op.drop_index(op.f("ix_recipe_line_pyme_id"), table_name="recipe_line")
    op.drop_table("recipe_line")
    op.drop_index(op.f("ix_quote_pyme_id"), table_name="quote")
    op.drop_table("quote")
    op.drop_index(op.f("ix_production_record_pyme_id"), table_name="production_record")
    op.drop_table("production_record")
    op.drop_index(op.f("ix_order_line_pyme_id"), table_name="order_line")
    op.drop_table("order_line")
    op.drop_index("uq_ingredient_price_current", table_name="ingredient_price", postgresql_where=sa.text("is_current"))
    op.drop_index(op.f("ix_ingredient_price_pyme_id"), table_name="ingredient_price")
    op.drop_table("ingredient_price")
    op.drop_index("ix_document_chunk_tsv", table_name="document_chunk", postgresql_using="gin")
    op.drop_index(op.f("ix_document_chunk_pyme_id"), table_name="document_chunk")
    op.drop_index(
        "ix_document_chunk_embedding",
        table_name="document_chunk",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("document_chunk")
    op.drop_index("uq_supplier_pyme_name", table_name="supplier")
    op.drop_index(op.f("ix_supplier_pyme_id"), table_name="supplier")
    op.drop_table("supplier")
    op.drop_index(op.f("ix_refresh_token_pyme_id"), table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_index(
        "uq_recipe_pyme_vision_class", table_name="recipe", postgresql_where=sa.text("vision_class IS NOT NULL")
    )
    op.drop_index("uq_recipe_pyme_name", table_name="recipe")
    op.drop_index(op.f("ix_recipe_pyme_id"), table_name="recipe")
    op.drop_table("recipe")
    op.drop_index("ix_metric_event_pyme_kind_created", table_name="metric_event")
    op.drop_index(op.f("ix_metric_event_pyme_id"), table_name="metric_event")
    op.drop_table("metric_event")
    op.drop_index("uq_ingredient_pyme_name", table_name="ingredient")
    op.drop_index(op.f("ix_ingredient_pyme_id"), table_name="ingredient")
    op.drop_table("ingredient")
    op.drop_index(op.f("ix_document_pyme_id"), table_name="document")
    op.drop_table("document")
    op.drop_index(op.f("ix_catering_order_pyme_id"), table_name="catering_order")
    op.drop_index("ix_catering_order_pyme_event", table_name="catering_order")
    op.drop_table("catering_order")
    op.drop_index(op.f("ix_cash_movement_pyme_id"), table_name="cash_movement")
    op.drop_table("cash_movement")
    op.drop_index(op.f("ix_assistant_interaction_pyme_id"), table_name="assistant_interaction")
    op.drop_table("assistant_interaction")
    op.drop_table("data_version")
    op.drop_index(op.f("ix_app_user_pyme_id"), table_name="app_user")
    op.drop_table("app_user")
    op.drop_table("pyme")
    op.drop_index(op.f("ix_login_attempt_ip"), table_name="login_attempt")
    op.drop_index(op.f("ix_login_attempt_email"), table_name="login_attempt")
    op.drop_index(op.f("ix_login_attempt_created_at"), table_name="login_attempt")
    op.drop_table("login_attempt")

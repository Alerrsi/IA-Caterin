"""existencias de productos terminados (T18, ADR-011)

- `product_movement`: libro de movimientos de productos terminados (solo crece); `recipe.stock_qty` es su saldo.
- `production_record.consumed_ingredients` y `voided_at`: si la producción descontó insumos y cuándo se anuló.
- `pyme.production_consumes_ingredients`: al confirmar una producción se descuentan los insumos (por defecto, sí).
Las producciones anteriores quedan con `consumed_ingredients = false` y no suman existencias: no se reescribe el pasado.

Revision ID: a350bad426a3
Revises: 3f9c1a7d2b64
Create Date: 2026-11-16 22:19:44.832545
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a350bad426a3"
down_revision: str | None = "3f9c1a7d2b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_movement",
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("delta_qty", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "production",
                "delivery",
                "adjustment",
                "waste",
                "void",
                name="product_movement_reason",
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
        sa.CheckConstraint("delta_qty <> 0", name=op.f("ck_product_movement_delta_not_zero")),
        sa.ForeignKeyConstraint(
            ["pyme_id", "created_by"],
            ["app_user.pyme_id", "app_user.id"],
            name="fk_product_movement_created_by_app_user",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id", "recipe_id"],
            ["recipe.pyme_id", "recipe.id"],
            name="fk_product_movement_recipe_id_recipe",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pyme_id"], ["pyme.id"], name=op.f("fk_product_movement_pyme_id_pyme"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_movement")),
        sa.UniqueConstraint("pyme_id", "client_op_id", name="uq_product_movement_client_op"),
        sa.UniqueConstraint("pyme_id", "id", name="uq_product_movement_pyme_id_id"),
    )
    op.create_index(op.f("ix_product_movement_pyme_id"), "product_movement", ["pyme_id"], unique=False)
    op.create_index(
        "ix_product_movement_recipe_occurred", "product_movement", ["pyme_id", "recipe_id", "occurred_at"], unique=False
    )
    op.create_index(
        "ix_product_movement_reference", "product_movement", ["pyme_id", "reference_type", "reference_id"], unique=False
    )
    op.add_column(
        "production_record",
        sa.Column("consumed_ingredients", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("production_record", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "pyme",
        sa.Column("production_consumes_ingredients", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "recipe", sa.Column("stock_qty", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("recipe", "stock_qty")
    op.drop_column("pyme", "production_consumes_ingredients")
    op.drop_column("production_record", "voided_at")
    op.drop_column("production_record", "consumed_ingredients")
    op.drop_index("ix_product_movement_reference", table_name="product_movement")
    op.drop_index("ix_product_movement_recipe_occurred", table_name="product_movement")
    op.drop_index(op.f("ix_product_movement_pyme_id"), table_name="product_movement")
    op.drop_table("product_movement")

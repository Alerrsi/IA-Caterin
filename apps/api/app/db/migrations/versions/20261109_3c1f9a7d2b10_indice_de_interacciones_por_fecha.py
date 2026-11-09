"""indice de interacciones del asistente por fecha (panel de métricas T09)

Revision ID: 3c1f9a7d2b10
Revises: 896f42ac6856
Create Date: 2026-11-09 23:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3c1f9a7d2b10"
down_revision: str | None = "896f42ac6856"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_assistant_interaction_pyme_created",
        "assistant_interaction",
        ["pyme_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_interaction_pyme_created", table_name="assistant_interaction")

"""asistente: feedback y dominio de datos 'production'

Revision ID: c4a7e2d91b30
Revises: 3c1f9a7d2b10
Create Date: 2026-11-09 21:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a7e2d91b30"
down_revision: str | None = "3c1f9a7d2b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("inventory", "recipes", "suppliers", "orders", "cash", "documents")
NEW = (*OLD, "production")


def _domain_check(values: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_data_version_data_domain"), "data_version", type_="check")
    listed = ", ".join(f"'{v}'" for v in values)
    op.create_check_constraint(op.f("ck_data_version_data_domain"), "data_version", f"domain IN ({listed})")


def upgrade() -> None:
    _domain_check(NEW)
    op.execute(
        "INSERT INTO data_version (pyme_id, domain, version) SELECT id, 'production', 0 FROM pyme "
        "ON CONFLICT DO NOTHING"
    )
    op.add_column("assistant_interaction", sa.Column("feedback", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_assistant_interaction_feedback_range"),
        "assistant_interaction",
        "feedback IS NULL OR feedback IN (-1, 1)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_assistant_interaction_feedback_range"), "assistant_interaction", type_="check")
    op.drop_column("assistant_interaction", "feedback")
    op.execute("DELETE FROM data_version WHERE domain = 'production'")
    _domain_check(OLD)

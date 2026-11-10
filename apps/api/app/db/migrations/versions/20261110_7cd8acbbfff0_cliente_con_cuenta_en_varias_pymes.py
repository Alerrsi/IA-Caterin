"""cliente con cuenta en varias pymes (ADR-007): el cliente elige a qué pyme cotizar

El correo del equipo sigue siendo único en todo el sistema (índice parcial). Un cliente del portal tiene una cuenta
por pyme con el mismo correo (único por pyme).

Bajar la migración vuelve al correo único global: si un cliente tiene cuentas en varias pymes, se conserva la más
antigua y las demás quedan desactivadas con el correo marcado (`nombre+<pyme>@dominio`), sin borrar sus pedidos.

Revision ID: 7cd8acbbfff0
Revises: e161a90baaa3
Create Date: 2026-11-10 16:13:30.248142
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7cd8acbbfff0"
down_revision: str | None = "e161a90baaa3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("uq_app_user_email"), "app_user", type_="unique")
    op.create_unique_constraint(op.f("uq_app_user_pyme_email"), "app_user", ["pyme_id", "email"])
    op.create_index(
        "uq_app_user_staff_email", "app_user", ["email"], unique=True, postgresql_where=sa.text("role <> 'customer'")
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE app_user u
           SET email = split_part(u.email, '@', 1) || '+' || left(u.pyme_id::text, 8) || '@' || split_part(u.email, '@', 2),
               is_active = false
         WHERE u.role = 'customer'
           AND EXISTS (SELECT 1 FROM app_user o WHERE o.email = u.email AND o.created_at < u.created_at)
        """
    )
    op.drop_index("uq_app_user_staff_email", table_name="app_user", postgresql_where=sa.text("role <> 'customer'"))
    op.drop_constraint(op.f("uq_app_user_pyme_email"), "app_user", type_="unique")
    op.create_unique_constraint(op.f("uq_app_user_email"), "app_user", ["email"])

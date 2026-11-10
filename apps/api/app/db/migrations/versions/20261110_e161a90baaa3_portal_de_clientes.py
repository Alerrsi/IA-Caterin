"""portal de clientes (ADR-007): rol customer, pedidos del cliente y código de invitación de la pyme

- `app_user.role` admite `customer`.
- `catering_order.status` admite `customer_draft` (cotizado por el cliente, sin enviar) y `requested`
  (enviado, espera la decisión de la dueña). Nuevas columnas: quién lo pidió, cuándo lo envió y la respuesta.
- `pyme.customer_code`: código del enlace de registro de clientes.

Bajar la migración: los pedidos `customer_draft` pasan a `cancelled` y los `requested` a `draft` (la pyme no
pierde pedidos enviados), y las cuentas de clientes quedan **desactivadas** como `collaborator` (no se borran
porque los pedidos las referencian). Se pierden el código del portal y las respuestas a los clientes.

Revision ID: e161a90baaa3
Revises: 67b617a7b8cb
Create Date: 2026-11-10 15:00:12.687567
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e161a90baaa3"
down_revision: str | None = "67b617a7b8cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES_OLD = ("owner", "collaborator")
ROLES_NEW = (*ROLES_OLD, "customer")
STATUS_OLD = ("draft", "confirmed", "delivered", "cancelled")
STATUS_NEW = (*STATUS_OLD, "customer_draft", "requested")


def _check(values: tuple[str, ...], column: str) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_app_user_role"), "app_user", type_="check")
    op.create_check_constraint(op.f("ck_app_user_role"), "app_user", _check(ROLES_NEW, "role"))
    op.drop_constraint(op.f("ck_catering_order_order_status"), "catering_order", type_="check")
    op.create_check_constraint(op.f("ck_catering_order_order_status"), "catering_order", _check(STATUS_NEW, "status"))

    op.add_column("catering_order", sa.Column("customer_user_id", sa.Uuid(), nullable=True))
    op.add_column("catering_order", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("catering_order", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("catering_order", sa.Column("owner_message", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_catering_order_customer_user_id_app_user"),
        "catering_order",
        "app_user",
        ["pyme_id", "customer_user_id"],
        ["pyme_id", "id"],
    )
    op.create_index(
        "ix_catering_order_customer",
        "catering_order",
        ["pyme_id", "customer_user_id"],
        postgresql_where=sa.text("customer_user_id IS NOT NULL"),
    )
    op.add_column("pyme", sa.Column("customer_code", sa.String(length=32), nullable=True))
    op.create_unique_constraint(op.f("uq_pyme_customer_code"), "pyme", ["customer_code"])


def downgrade() -> None:
    op.execute("UPDATE catering_order SET status = 'cancelled' WHERE status = 'customer_draft'")
    op.execute("UPDATE catering_order SET status = 'draft' WHERE status = 'requested'")
    op.execute("UPDATE app_user SET role = 'collaborator', is_active = false WHERE role = 'customer'")

    op.drop_constraint(op.f("uq_pyme_customer_code"), "pyme", type_="unique")
    op.drop_column("pyme", "customer_code")
    op.drop_index("ix_catering_order_customer", table_name="catering_order")
    op.drop_constraint(op.f("fk_catering_order_customer_user_id_app_user"), "catering_order", type_="foreignkey")
    op.drop_column("catering_order", "owner_message")
    op.drop_column("catering_order", "decided_at")
    op.drop_column("catering_order", "submitted_at")
    op.drop_column("catering_order", "customer_user_id")

    op.drop_constraint(op.f("ck_catering_order_order_status"), "catering_order", type_="check")
    op.create_check_constraint(op.f("ck_catering_order_order_status"), "catering_order", _check(STATUS_OLD, "status"))
    op.drop_constraint(op.f("ck_app_user_role"), "app_user", type_="check")
    op.create_check_constraint(op.f("ck_app_user_role"), "app_user", _check(ROLES_OLD, "role"))

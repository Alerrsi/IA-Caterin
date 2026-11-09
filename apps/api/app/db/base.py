"""Base declarativa, tipos comunes y helpers de multi-tenancy (docs/DATA_MODEL.md)."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKeyConstraint,
    MetaData,
    Numeric,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Tipos de dominio: dinero en CLP sin decimales, cantidades con 3 decimales en unidad base.
Money = Numeric(12, 0)
Quantity = Numeric(14, 3)
Percent = Numeric(5, 2)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {Decimal: Numeric(14, 3), uuid.UUID: Uuid}


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Enum guardado como texto con CHECK (más fácil de migrar que un ENUM nativo de Postgres)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantMixin(TimestampMixin):
    """Columnas comunes de toda tabla de negocio. Ver reglas de multi-tenancy en DATA_MODEL.md."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pyme_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(default=None)


def tenant_args(table: str, *fks: tuple[str, str, str | None], extra: tuple[Any, ...] = ()) -> tuple[Any, ...]:
    """Restricciones de tenant para `__table_args__`.

    - FK simple de `pyme_id` a `pyme.id`.
    - UNIQUE(pyme_id, id) para que otras tablas puedan apuntar con FK compuesta.
    - FK compuesta (pyme_id, col) -> (pyme_id, id) por cada relación: la base impide referencias entre pymes.
      `fks` son tuplas (columna, tabla_destino, ondelete).
    - FK compuesta de `created_by` al usuario de la misma pyme.
    """
    constraints: list[Any] = [
        ForeignKeyConstraint(["pyme_id"], ["pyme.id"], ondelete="CASCADE"),
        UniqueConstraint("pyme_id", "id", name=f"uq_{table}_pyme_id_id"),
        ForeignKeyConstraint(
            ["pyme_id", "created_by"],
            ["app_user.pyme_id", "app_user.id"],
            name=f"fk_{table}_created_by_app_user",
        ),
    ]
    for column, target, ondelete in fks:
        constraints.append(
            ForeignKeyConstraint(
                ["pyme_id", column],
                [f"{target}.pyme_id", f"{target}.id"],
                ondelete=ondelete,
                name=f"fk_{table}_{column}_{target}",
            )
        )
    return (*constraints, *extra)

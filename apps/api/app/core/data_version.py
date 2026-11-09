"""Versión de datos por pyme y dominio, para invalidar la caché del asistente (ADR-005)."""

import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.enums import DataDomain
from app.db.models import DataVersion


def init_versions(db: Session, pyme_id: uuid.UUID) -> None:
    db.add_all(DataVersion(pyme_id=pyme_id, domain=d, version=0) for d in DataDomain)


def bump(db: Session, *domains: DataDomain) -> None:
    """Incrementa la versión en la misma transacción de la escritura (usa el tenant de la sesión)."""
    pyme_id = db.info["pyme_id"]
    db.execute(
        update(DataVersion)
        .where(DataVersion.pyme_id == pyme_id, DataVersion.domain.in_(domains))
        .values(version=DataVersion.version + 1)
    )

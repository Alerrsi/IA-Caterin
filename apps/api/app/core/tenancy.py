"""Multi-tenancy central (docs/DATA_MODEL.md, sección 4; docs/SECURITY.md, sección 1).

- El `pyme_id` sale SOLO del JWT.
- `get_tenant_db` entrega una sesión que filtra automáticamente por `pyme_id` toda consulta ORM
  (SELECT, UPDATE y DELETE) sobre tablas de negocio, y que al hacer flush asigna `pyme_id` y
  `created_by` a los objetos nuevos y rechaza cualquier objeto de otra pyme.
- Los módulos NO escriben `where(pyme_id == ...)` a mano.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from sqlalchemy import event, select
from sqlalchemy.orm import ORMExecuteState, Session, UOWTransaction, with_loader_criteria

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.db.base import TenantMixin
from app.db.enums import Role
from app.db.models import User
from app.db.session import get_sessionmaker

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - tipo de token, no un secreto


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    pyme_id: uuid.UUID
    role: Role
    email: str
    full_name: str

    @property
    def is_owner(self) -> bool:
        return self.role == Role.OWNER


class TenantViolationError(RuntimeError):
    """Se intentó escribir un objeto de otra pyme con una sesión de tenant."""


def _unauthorized(detail: str = "Inicia sesión de nuevo.") -> ProblemError:
    return ProblemError(401, "unauthorized", "Necesitas iniciar sesión", detail)


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_criteria(state: ORMExecuteState) -> None:
    pyme_id = state.session.info.get("pyme_id")
    if pyme_id is None or not (state.is_select or state.is_update or state.is_delete):
        return
    if state.execution_options.get("skip_tenant_filter"):
        return
    state.statement = state.statement.options(
        with_loader_criteria(TenantMixin, lambda cls: cls.pyme_id == pyme_id, include_aliases=True)
    )


@event.listens_for(Session, "before_flush")
def _enforce_tenant_on_write(session: Session, _ctx: UOWTransaction, _instances: Any) -> None:
    pyme_id = session.info.get("pyme_id")
    if pyme_id is None:
        return
    user_id = session.info.get("user_id")
    for obj in session.new:
        if isinstance(obj, TenantMixin):
            if obj.pyme_id is None:
                obj.pyme_id = pyme_id
            if obj.created_by is None and user_id is not None:
                obj.created_by = user_id
    for obj in (*session.new, *session.dirty, *session.deleted):
        if isinstance(obj, TenantMixin) and obj.pyme_id != pyme_id:
            raise TenantViolationError("Objeto de otra pyme en una sesión de tenant")


def open_tenant_session(pyme_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Session:
    session = get_sessionmaker()()
    session.info["pyme_id"] = pyme_id
    session.info["user_id"] = user_id
    return session


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "pyme_id", "role", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Tu sesión venció. Vuelve a entrar.") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise _unauthorized()
    return claims


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    return token


def get_session_user(request: Request) -> CurrentUser:
    """Cualquier cuenta activa, incluidos los clientes del portal. Solo para /auth/me y el portal."""
    claims = decode_access_token(_bearer_token(request))
    try:
        user_id = uuid.UUID(claims["sub"])
        pyme_id = uuid.UUID(claims["pyme_id"])
    except (ValueError, TypeError) as exc:
        raise _unauthorized() from exc
    # Se revisa en la base que la usuaria siga activa y pertenezca a la pyme del token.
    with get_sessionmaker()() as session:
        user = session.scalar(select(User).where(User.id == user_id, User.pyme_id == pyme_id))
    if user is None or not user.is_active:
        raise _unauthorized()
    return CurrentUser(user.id, user.pyme_id, user.role, user.email, user.full_name)


SessionUserDep = Annotated[CurrentUser, Depends(get_session_user)]


def get_current_user(user: SessionUserDep) -> CurrentUser:
    """La dueña o una colaboradora. Un cliente del portal (ADR-007) no entra a ninguna ruta de la pyme: todas
    usan esta dependencia (o `require_owner`), así que el bloqueo es central y no depende de cada módulo."""
    if user.role == Role.CUSTOMER:
        raise ProblemError(403, "staff_only", "Esta sección es solo para la pyme")
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def get_tenant_db(user: CurrentUserDep) -> Iterator[Session]:
    session = open_tenant_session(user.pyme_id, user.id)
    try:
        yield session
    finally:
        session.close()


TenantDB = Annotated[Session, Depends(get_tenant_db)]


def require_owner(user: CurrentUserDep) -> CurrentUser:
    if not user.is_owner:
        raise ProblemError(403, "owner_only", "Solo la dueña puede hacer esto")
    return user


OwnerDep = Annotated[CurrentUser, Depends(require_owner)]


def require_customer(user: SessionUserDep) -> CurrentUser:
    if user.role != Role.CUSTOMER:
        raise ProblemError(403, "customer_only", "Esta sección es para los clientes de la pyme")
    return user


CustomerDep = Annotated[CurrentUser, Depends(require_customer)]


def get_customer_db(user: CustomerDep) -> Iterator[Session]:
    """Sesión de tenant del cliente: ve solo su pyme. Lo suyo dentro de ella lo filtra el portal."""
    session = open_tenant_session(user.pyme_id, user.id)
    try:
        yield session
    finally:
        session.close()


CustomerDB = Annotated[Session, Depends(get_customer_db)]

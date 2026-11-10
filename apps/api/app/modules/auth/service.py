"""Registro, login, tokens y gestión de usuarias (docs/SECURITY.md, sección 2)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.data_version import init_versions
from app.core.errors import ProblemError, not_found
from app.core.security import hash_password, needs_rehash, verify_password
from app.core.tenancy import ACCESS_TOKEN_TYPE, CurrentUser
from app.db.enums import Role
from app.db.models import LoginAttempt, Pyme, RefreshToken, User
from app.modules.auth.schemas import (
    PymeOut,
    PymePublicOut,
    PymeUpdate,
    RegisterIn,
    TokenOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

REFRESH_COOKIE = "caterin_refresh"
REFRESH_PATH = "/api/v1/auth"

_INVALID_LOGIN = ProblemError(401, "invalid_credentials", "Correo o contraseña incorrectos")


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == email).execution_options(skip_tenant_filter=True)) is not None


# --------------------------------------------------------------------------- registro y login


def register(db: Session, data: RegisterIn) -> User:
    if _email_taken(db, data.email):
        raise ProblemError(409, "email_taken", "Ese correo ya tiene una cuenta", "Prueba iniciar sesión.")
    pyme = Pyme(name=data.pyme_name.strip(), commune=data.commune)
    db.add(pyme)
    db.flush()
    user = User(
        pyme_id=pyme.id,
        email=data.email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        role=Role.OWNER,
    )
    db.add(user)
    init_versions(db, pyme.id)
    db.commit()
    return user


def _check_rate_limit(db: Session, email: str, ip: str) -> None:
    settings = get_settings()
    since = _now() - timedelta(minutes=settings.login_window_min)
    by_email, by_ip = db.execute(
        select(
            func.count().filter(LoginAttempt.email == email),
            func.count().filter(LoginAttempt.ip == ip),
        ).where(LoginAttempt.created_at >= since, or_(LoginAttempt.email == email, LoginAttempt.ip == ip))
    ).one()
    if by_email >= settings.login_max_attempts or by_ip >= settings.login_max_attempts * 5:
        raise ProblemError(
            429,
            "too_many_attempts",
            "Demasiados intentos, espera un momento",
            f"Vuelve a intentar en {settings.login_window_min} minutos.",
        )


def authenticate(db: Session, email: str, password: str, ip: str) -> User:
    _check_rate_limit(db, email, ip)
    # Un cliente del portal puede tener una cuenta por pyme con el mismo correo (ADR-007): se entra con la más
    # antigua activa (todas comparten la contraseña) y el portal le muestra todas sus pymes.
    user = db.scalar(
        select(User)
        .where(User.email == email)
        .order_by(User.is_active.desc(), (User.role == Role.CUSTOMER).asc(), User.created_at)
        .limit(1)
    )
    ok = user is not None and user.is_active and verify_password(user.password_hash, password)
    if not ok or user is None:
        db.add(LoginAttempt(email=email, ip=ip))
        db.commit()
        raise _INVALID_LOGIN
    db.execute(delete(LoginAttempt).where(LoginAttempt.email == email))
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    db.commit()
    return user


# --------------------------------------------------------------------------- tokens


def create_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    ttl = settings.jwt_access_ttl_min * 60
    now = _now()
    claims = {
        "sub": str(user.id),
        "pyme_id": str(user.pyme_id),
        "role": user.role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256"), ttl


def issue_refresh_token(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        RefreshToken(
            pyme_id=user.pyme_id,
            user_id=user.id,
            token_hash=_hash_token(raw),
            expires_at=_now() + timedelta(days=get_settings().jwt_refresh_ttl_days),
        )
    )
    db.commit()
    return raw


def rotate_refresh_token(db: Session, raw: str | None) -> tuple[User, str]:
    """Revoca el refresh usado y entrega uno nuevo. Si se reutiliza uno revocado, revoca todos los de la usuaria."""
    expired = ProblemError(401, "session_expired", "Tu sesión venció", "Vuelve a iniciar sesión.")
    if not raw:
        raise expired
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash_token(raw)))
    if token is None:
        raise expired
    if token.revoked_at is not None:
        _revoke_all(db, token.user_id)
        db.commit()
        raise expired
    if token.expires_at <= _now():
        raise expired
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise expired
    token.revoked_at = _now()
    db.flush()
    return user, issue_refresh_token(db, user)


def revoke_refresh_token(db: Session, raw: str | None) -> None:
    if not raw:
        return
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == _hash_token(raw), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    db.commit()


def _revoke_all(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
        .execution_options(skip_tenant_filter=True)
    )


# --------------------------------------------------------------------------- pyme y usuarias (sesión de tenant)


def get_pyme(db: Session, current: CurrentUser) -> Pyme:
    pyme = db.get(Pyme, current.pyme_id)
    if pyme is None:  # pragma: no cover - la usuaria existe, su pyme también
        raise not_found("pyme_not_found")
    return pyme


def update_pyme(db: Session, current: CurrentUser, data: PymeUpdate) -> Pyme:
    pyme = get_pyme(db, current)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in {"name", "vat_pct", "default_waste_pct", "prices_include_vat"} and value is None:
            continue
        setattr(pyme, field, value)
    db.commit()
    db.refresh(pyme)
    return pyme


def list_users(db: Session) -> list[User]:
    """El equipo de la pyme (sin los clientes del portal)."""
    return list(db.scalars(select(User).where(User.role != Role.CUSTOMER).order_by(User.created_at)))


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("user_not_found", "No encontramos a esa usuaria")
    return user


def create_user(db: Session, data: UserCreate) -> User:
    if _email_taken(db, data.email):
        raise ProblemError(409, "email_taken", "Ese correo ya tiene una cuenta")
    user = User(
        email=data.email, full_name=data.full_name.strip(), password_hash=hash_password(data.password), role=data.role
    )
    db.add(user)
    db.commit()
    return user


def _active_owners(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User).where(User.role == Role.OWNER, User.is_active)) or 0)


def update_user(db: Session, current: CurrentUser, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    if user.role == Role.CUSTOMER:  # un cliente no se convierte en parte del equipo desde aquí
        raise not_found("user_not_found", "No encontramos a esa usuaria")
    changes = data.model_dump(exclude_unset=True)
    demotes_owner = user.role == Role.OWNER and changes.get("role") == Role.COLLABORATOR
    deactivates_owner = user.role == Role.OWNER and changes.get("is_active") is False
    if (demotes_owner or deactivates_owner) and _active_owners(db) <= 1:
        raise ProblemError(409, "last_owner", "La pyme necesita al menos una dueña activa")
    if user.id == current.id and changes.get("is_active") is False:
        raise ProblemError(409, "cannot_deactivate_self", "No puedes desactivar tu propia cuenta")
    if changes.get("full_name"):
        user.full_name = changes["full_name"].strip()
    if changes.get("role"):
        user.role = changes["role"]
    if changes.get("password"):
        user.password_hash = hash_password(changes["password"])
        _revoke_all(db, user.id)
    if "is_active" in changes and changes["is_active"] is not None:
        user.is_active = changes["is_active"]
        if not user.is_active:
            _revoke_all(db, user.id)
    db.commit()
    return user


def deactivate_user(db: Session, current: CurrentUser, user_id: uuid.UUID) -> None:
    update_user(db, current, user_id, UserUpdate(is_active=False))


def new_customer_code(db: Session, current: CurrentUser) -> Pyme:
    """Crea (o cambia) el código del enlace del portal. El código anterior deja de servir."""
    pyme = get_pyme(db, current)
    pyme.customer_code = secrets.token_urlsafe(9)
    db.commit()
    db.refresh(pyme)
    return pyme


def close_customer_portal(db: Session, current: CurrentUser) -> Pyme:
    """Sin código no se registran clientes nuevos; los ya registrados siguen entrando."""
    pyme = get_pyme(db, current)
    pyme.customer_code = None
    db.commit()
    db.refresh(pyme)
    return pyme


# --------------------------------------------------------------------------- sesión (la usa también el portal)


def _set_refresh_cookie(response: Response, raw: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.jwt_refresh_ttl_days * 86400,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path=REFRESH_PATH,
    )


def token_response(db: Session, response: Response, user: User, refresh: str | None = None) -> TokenOut:
    access, ttl = create_access_token(user)
    _set_refresh_cookie(response, refresh or issue_refresh_token(db, user))
    pyme = db.get(Pyme, user.pyme_id)
    return TokenOut(access_token=access, expires_in=ttl, user=UserOut.model_validate(user), pyme=pyme_view(user, pyme))


def pyme_view(user: User, pyme: Pyme | None) -> PymeOut | PymePublicOut:
    """Un cliente del portal no ve el margen ni la configuración interna de la pyme (ADR-007)."""
    if user.role == Role.CUSTOMER:
        return PymePublicOut.model_validate(pyme)
    return PymeOut.model_validate(pyme)

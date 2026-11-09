import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenancy import CurrentUserDep, OwnerDep, TenantDB
from app.db.models import Pyme, User
from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.schemas import (
    LoginIn,
    MeOut,
    PymeOut,
    PymeUpdate,
    RegisterIn,
    TokenOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

REFRESH_COOKIE = "caterin_refresh"
REFRESH_PATH = "/api/v1/auth"

router = APIRouter(tags=["auth"])
DB = Annotated[Session, Depends(get_db)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


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


def _token_response(db: Session, response: Response, user: User, refresh: str | None = None) -> TokenOut:
    access, ttl = service.create_access_token(user)
    _set_refresh_cookie(response, refresh or service.issue_refresh_token(db, user))
    pyme = db.get(Pyme, user.pyme_id)
    return TokenOut(
        access_token=access,
        expires_in=ttl,
        user=UserOut.model_validate(user),
        pyme=PymeOut.model_validate(pyme),
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, response: Response, db: DB) -> TokenOut:
    """Crea la pyme y su cuenta de dueña."""
    user = service.register(db, data)
    return _token_response(db, response, user)


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, response: Response, db: DB) -> TokenOut:
    user = service.authenticate(db, data.email, data.password, _client_ip(request))
    return _token_response(db, response, user)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(response: Response, db: DB, caterin_refresh: RefreshCookie = None) -> TokenOut:
    user, new_refresh = service.rotate_refresh_token(db, caterin_refresh)
    return _token_response(db, response, user, new_refresh)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: DB, caterin_refresh: RefreshCookie = None) -> Response:
    service.revoke_refresh_token(db, caterin_refresh)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    return response


@router.get("/auth/me", response_model=MeOut)
def me(current: CurrentUserDep, db: TenantDB) -> MeOut:
    user = service.get_user(db, current.id)
    return MeOut(user=UserOut.model_validate(user), pyme=PymeOut.model_validate(service.get_pyme(db, current)))


@router.get("/pyme", response_model=PymeOut, tags=["pyme"])
def get_pyme(current: CurrentUserDep, db: TenantDB) -> Pyme:
    return service.get_pyme(db, current)


@router.patch("/pyme", response_model=PymeOut, tags=["pyme"])
def update_pyme(data: PymeUpdate, owner: OwnerDep, db: TenantDB) -> Pyme:
    return service.update_pyme(db, owner, data)


@router.get("/users", response_model=list[UserOut], tags=["usuarias"])
def list_users(_owner: OwnerDep, db: TenantDB) -> list[User]:
    return service.list_users(db)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, tags=["usuarias"])
def create_user(data: UserCreate, _owner: OwnerDep, db: TenantDB) -> User:
    """Crea una colaboradora (o otra dueña) con una contraseña inicial que la dueña le entrega."""
    return service.create_user(db, data)


@router.patch("/users/{user_id}", response_model=UserOut, tags=["usuarias"])
def update_user(user_id: uuid.UUID, data: UserUpdate, owner: OwnerDep, db: TenantDB) -> User:
    return service.update_user(db, owner, user_id, data)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["usuarias"])
def deactivate_user(user_id: uuid.UUID, owner: OwnerDep, db: TenantDB) -> Response:
    """Desactiva la cuenta (no se borra, para mantener la trazabilidad)."""
    service.deactivate_user(db, owner, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

import re
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.db.enums import Role

COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "contraseña1",
        "contrasena1",
        "password123",
        "qwertyuiop",
        "catering123",
        "temuco12345",
        "chile123456",
        "0987654321",
        "1111111111",
        "abcdefghij",
    }
)


_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def _check_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("El correo no es válido")
    return value


Email = Annotated[str, AfterValidator(_check_email)]


def _check_password(value: str) -> str:
    if value.lower() in COMMON_PASSWORDS:
        raise ValueError("Esa contraseña es muy común; elige otra")
    return value


PasswordStr = Annotated[str, Field(min_length=10, max_length=128), AfterValidator(_check_password)]


class PymeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rut: str | None
    commune: str | None
    default_waste_pct: Decimal
    default_margin_pct: Decimal | None
    vat_pct: Decimal
    prices_include_vat: bool
    quote_validity_days: int | None
    is_demo: bool
    customer_code: str | None = None


class PymePublicOut(BaseModel):
    """Lo que ve un cliente del portal (ADR-007): sin margen, merma ni otros datos internos."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    commune: str | None
    vat_pct: Decimal
    is_demo: bool


class PymeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    rut: str | None = Field(default=None, max_length=12)
    commune: str | None = Field(default=None, max_length=80)
    default_waste_pct: Decimal | None = Field(default=None, ge=0, lt=100)
    default_margin_pct: Decimal | None = Field(default=None, ge=0, le=1000)
    vat_pct: Decimal | None = Field(default=None, ge=0, lt=100)
    prices_include_vat: bool | None = None
    quote_validity_days: int | None = Field(default=None, ge=1, le=365)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool


class RegisterIn(BaseModel):
    pyme_name: str = Field(min_length=2, max_length=120)
    commune: str | None = Field(default=None, max_length=80)
    full_name: str = Field(min_length=2, max_length=120)
    email: Email
    password: PasswordStr


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - tipo OAuth2, no un secreto
    expires_in: int
    user: UserOut
    pyme: PymeOut | PymePublicOut


class MeOut(BaseModel):
    user: UserOut
    pyme: PymeOut | PymePublicOut


# Las cuentas del equipo; los clientes se registran solos por el enlace del portal (ADR-007).
StaffRole = Literal[Role.OWNER, Role.COLLABORATOR]


class UserCreate(BaseModel):
    email: Email
    full_name: str = Field(min_length=2, max_length=120)
    password: PasswordStr
    role: StaffRole = Role.COLLABORATOR


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: StaffRole | None = None
    is_active: bool | None = None
    password: PasswordStr | None = None

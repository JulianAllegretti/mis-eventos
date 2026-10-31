from dataclasses import dataclass
from typing import Literal

from app.domain.models.user import User


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    token: str
    expires_in: int  # segundos de vida del token


ReadinessStatus = Literal["ok", "degraded", "unavailable"]


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    status: ReadinessStatus
    checks: dict[str, bool]


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: list[T]
    total: int
    page: int
    page_size: int

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domain.models.event import Event
from app.domain.models.registration import Registration
from app.domain.models.session import Session
from app.domain.models.speaker import Speaker
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


@dataclass(frozen=True, slots=True)
class SessionView:
    session: Session
    speaker: Speaker | None


@dataclass(frozen=True, slots=True)
class MyRegistration:
    event: Event
    registered_at: datetime
    sessions: list[SessionView]


@dataclass(frozen=True, slots=True)
class AttendeeView:
    registration: Registration
    user: User

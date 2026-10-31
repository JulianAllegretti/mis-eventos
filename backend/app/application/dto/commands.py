from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.models.user import User


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    full_name: str


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str


# --- Eventos ---


@dataclass(frozen=True, slots=True)
class CreateEventCommand:
    actor: User
    name: str
    description: str | None
    location: str
    start_at: datetime
    end_at: datetime
    capacity: int


@dataclass(frozen=True, slots=True)
class UpdateEventCommand:
    actor: User
    event_id: UUID
    changes: Mapping[str, Any]  # solo los campos enviados por el cliente


@dataclass(frozen=True, slots=True)
class EventActionCommand:
    """Publicar, finalizar, cancelar o borrar un evento."""

    actor: User
    event_id: UUID


# --- Ponentes ---


@dataclass(frozen=True, slots=True)
class CreateSpeakerCommand:
    actor: User
    name: str
    email: str | None
    bio: str | None


@dataclass(frozen=True, slots=True)
class UpdateSpeakerCommand:
    actor: User
    speaker_id: UUID
    changes: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SpeakerActionCommand:
    actor: User
    speaker_id: UUID


# --- Administración de usuarios ---


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    actor: User
    user_id: UUID
    changes: Mapping[str, Any]  # claves permitidas: role, is_active

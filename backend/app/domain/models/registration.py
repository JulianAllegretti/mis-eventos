from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4


@dataclass(slots=True)
class Registration:
    """Inscripción de un usuario a un evento. Cancelar la deja registrada con cancelled_at."""

    id: UUID
    user_id: UUID
    event_id: UUID
    created_at: datetime
    cancelled_at: datetime | None = None

    @classmethod
    def new(cls, *, user_id: UUID, event_id: UUID, now: datetime) -> Self:
        return cls(id=uuid4(), user_id=user_id, event_id=event_id, created_at=now)


@dataclass(slots=True)
class SessionRegistration:
    id: UUID
    user_id: UUID
    session_id: UUID
    created_at: datetime
    cancelled_at: datetime | None = None

    @classmethod
    def new(cls, *, user_id: UUID, session_id: UUID, now: datetime) -> Self:
        return cls(id=uuid4(), user_id=user_id, session_id=session_id, created_at=now)

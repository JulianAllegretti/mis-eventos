from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID, uuid4


@dataclass(slots=True)
class Session:
    """Una charla, taller o bloque de la agenda de un evento (no confundir con sesión de login)."""

    id: UUID
    event_id: UUID
    speaker_id: UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    capacity: int
    registered_count: int
    created_at: datetime

    @classmethod
    def new(
        cls,
        *,
        event_id: UUID,
        speaker_id: UUID,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        capacity: int,
        now: datetime,
    ) -> Self:
        return cls(
            id=uuid4(),
            event_id=event_id,
            speaker_id=speaker_id,
            title=title,
            description=description,
            start_at=start_at,
            end_at=end_at,
            capacity=capacity,
            registered_count=0,
            created_at=now,
        )

    @property
    def available_slots(self) -> int:
        return self.capacity - self.registered_count

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID, uuid4


class EventStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class ClosedSource(StrEnum):
    MANUAL = "manual"
    SCHEDULER = "scheduler"


@dataclass(slots=True)
class Event:
    id: UUID
    name: str
    description: str | None
    location: str
    start_at: datetime
    end_at: datetime
    capacity: int
    registered_count: int
    status: EventStatus
    organizer_id: UUID
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    closed_by_id: UUID | None = None
    closed_source: ClosedSource | None = None

    @classmethod
    def new(
        cls,
        *,
        name: str,
        description: str | None,
        location: str,
        start_at: datetime,
        end_at: datetime,
        capacity: int,
        organizer_id: UUID,
        now: datetime,
    ) -> Self:
        return cls(
            id=uuid4(),
            name=name,
            description=description,
            location=location,
            start_at=start_at,
            end_at=end_at,
            capacity=capacity,
            registered_count=0,
            status=EventStatus.DRAFT,
            organizer_id=organizer_id,
            created_at=now,
            updated_at=now,
        )

    @property
    def available_slots(self) -> int:
        return self.capacity - self.registered_count

    def effective_status(self, now: datetime) -> EventStatus:
        """Un evento publicado cuya fecha fin ya pasó se considera finalizado (ADR 0008)."""
        if self.status is EventStatus.PUBLISHED and self.end_at < now:
            return EventStatus.FINISHED
        return self.status

    def with_effective_status(self, now: datetime) -> Self:
        return replace(self, status=self.effective_status(now))

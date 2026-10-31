from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.event import ClosedSource, EventStatus


class EventCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    location: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime
    capacity: int = Field(ge=1, le=100_000)


class EventUpdateRequest(BaseModel):
    """PATCH parcial: solo se aplican los campos enviados."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    start_at: datetime | None = None
    end_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=1, le=100_000)


class EventResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    location: str
    start_at: datetime
    end_at: datetime
    capacity: int
    registered_count: int
    available_slots: int
    status: EventStatus
    organizer_id: UUID
    closed_at: datetime | None
    closed_by_id: UUID | None
    closed_source: ClosedSource | None
    created_at: datetime
    updated_at: datetime


class EventPage(BaseModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int

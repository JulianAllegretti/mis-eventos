from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.adapters.inbound.http.schemas.events import EventResponse


class SessionCreateRequest(BaseModel):
    speaker_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    start_at: datetime
    end_at: datetime
    capacity: int = Field(ge=1, le=100_000)


class SessionUpdateRequest(BaseModel):
    """PATCH parcial: solo se aplican los campos enviados."""

    speaker_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=1, le=100_000)


class SpeakerSummary(BaseModel):
    """Datos públicos del ponente: no incluye el correo."""

    id: UUID
    name: str
    bio: str | None


class SessionResponse(BaseModel):
    id: UUID
    event_id: UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    capacity: int
    registered_count: int
    available_slots: int
    speaker: SpeakerSummary | None


class SessionRegistrationResponse(BaseModel):
    id: UUID
    session_id: UUID
    created_at: datetime


class RegistrationResponse(BaseModel):
    id: UUID
    event_id: UUID
    created_at: datetime


class MyRegistrationResponse(BaseModel):
    event: EventResponse
    registered_at: datetime
    sessions: list[SessionResponse]


class AttendeeResponse(BaseModel):
    registration_id: UUID
    user_id: UUID
    full_name: str
    email: str
    registered_at: datetime


class AttendeePage(BaseModel):
    items: list[AttendeeResponse]
    total: int
    page: int
    page_size: int

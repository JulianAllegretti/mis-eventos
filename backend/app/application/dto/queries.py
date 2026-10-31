from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.models.event import EventStatus
from app.domain.models.user import User

MAX_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class GetEventQuery:
    viewer: User | None
    event_id: UUID


@dataclass(frozen=True, slots=True)
class SearchEventsQuery:
    viewer: User | None
    q: str | None = None
    status: EventStatus | None = None
    mine: bool = False  # incluye los borradores propios
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class EventSearchCriteria:
    """Criterio ya resuelto que recibe el repositorio."""

    now: datetime
    q: str | None
    status: EventStatus | None
    organizer_id: UUID | None
    exclude_drafts: bool
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class GetSpeakerQuery:
    actor: User
    speaker_id: UUID


@dataclass(frozen=True, slots=True)
class ListSpeakersQuery:
    actor: User
    q: str | None = None
    page: int = 1
    page_size: int = 20


@dataclass(frozen=True, slots=True)
class ListUsersQuery:
    actor: User
    q: str | None = None
    page: int = 1
    page_size: int = 20

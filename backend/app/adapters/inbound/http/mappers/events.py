from uuid import UUID

from app.adapters.inbound.http.schemas.events import (
    EventCreateRequest,
    EventPage,
    EventResponse,
    EventUpdateRequest,
)
from app.application.dto.commands import CreateEventCommand, UpdateEventCommand
from app.application.dto.read_models import Page
from app.domain.models.event import Event
from app.domain.models.user import User


def to_create_event_command(body: EventCreateRequest, actor: User) -> CreateEventCommand:
    return CreateEventCommand(
        actor=actor,
        name=body.name,
        description=body.description,
        location=body.location,
        start_at=body.start_at,
        end_at=body.end_at,
        capacity=body.capacity,
    )


def to_update_event_command(
    event_id: UUID, body: EventUpdateRequest, actor: User
) -> UpdateEventCommand:
    return UpdateEventCommand(
        actor=actor, event_id=event_id, changes=body.model_dump(exclude_unset=True)
    )


def to_event_response(event: Event) -> EventResponse:
    return EventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        location=event.location,
        start_at=event.start_at,
        end_at=event.end_at,
        capacity=event.capacity,
        registered_count=event.registered_count,
        available_slots=event.available_slots,
        status=event.status,
        organizer_id=event.organizer_id,
        closed_at=event.closed_at,
        closed_by_id=event.closed_by_id,
        closed_source=event.closed_source,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def to_event_page(page: Page[Event]) -> EventPage:
    return EventPage(
        items=[to_event_response(e) for e in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )

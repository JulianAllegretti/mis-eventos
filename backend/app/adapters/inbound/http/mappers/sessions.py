from uuid import UUID

from app.adapters.inbound.http.mappers.events import to_event_response
from app.adapters.inbound.http.schemas.sessions import (
    AttendeePage,
    AttendeeResponse,
    MyRegistrationResponse,
    RegistrationResponse,
    SessionCreateRequest,
    SessionRegistrationResponse,
    SessionResponse,
    SessionUpdateRequest,
    SpeakerSummary,
)
from app.application.dto.commands import CreateSessionCommand, UpdateSessionCommand
from app.application.dto.read_models import AttendeeView, MyRegistration, Page, SessionView
from app.domain.models.registration import Registration, SessionRegistration
from app.domain.models.user import User


def to_create_session_command(
    event_id: UUID, body: SessionCreateRequest, actor: User
) -> CreateSessionCommand:
    return CreateSessionCommand(
        actor=actor,
        event_id=event_id,
        speaker_id=body.speaker_id,
        title=body.title,
        description=body.description,
        start_at=body.start_at,
        end_at=body.end_at,
        capacity=body.capacity,
    )


def to_update_session_command(
    session_id: UUID, body: SessionUpdateRequest, actor: User
) -> UpdateSessionCommand:
    return UpdateSessionCommand(
        actor=actor, session_id=session_id, changes=body.model_dump(exclude_unset=True)
    )


def to_session_response(view: SessionView) -> SessionResponse:
    session, speaker = view.session, view.speaker
    return SessionResponse(
        id=session.id,
        event_id=session.event_id,
        title=session.title,
        description=session.description,
        start_at=session.start_at,
        end_at=session.end_at,
        capacity=session.capacity,
        registered_count=session.registered_count,
        available_slots=session.available_slots,
        speaker=SpeakerSummary(id=speaker.id, name=speaker.name, bio=speaker.bio)
        if speaker
        else None,
    )


def to_registration_response(registration: Registration) -> RegistrationResponse:
    return RegistrationResponse(
        id=registration.id, event_id=registration.event_id, created_at=registration.created_at
    )


def to_session_registration_response(
    registration: SessionRegistration,
) -> SessionRegistrationResponse:
    return SessionRegistrationResponse(
        id=registration.id, session_id=registration.session_id, created_at=registration.created_at
    )


def to_my_registration_response(item: MyRegistration) -> MyRegistrationResponse:
    return MyRegistrationResponse(
        event=to_event_response(item.event),
        registered_at=item.registered_at,
        sessions=[to_session_response(v) for v in item.sessions],
    )


def to_attendee_page(page: Page[AttendeeView]) -> AttendeePage:
    return AttendeePage(
        items=[
            AttendeeResponse(
                registration_id=a.registration.id,
                user_id=a.user.id,
                full_name=a.user.full_name,
                email=a.user.email,
                registered_at=a.registration.created_at,
            )
            for a in page.items
        ],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )

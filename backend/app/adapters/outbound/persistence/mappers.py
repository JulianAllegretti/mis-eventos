"""Traducción entre filas de tabla y entidades de dominio."""

from app.adapters.outbound.persistence.tables import EventTable, SpeakerTable, UserTable
from app.domain.models.event import ClosedSource, Event, EventStatus
from app.domain.models.speaker import Speaker
from app.domain.models.user import Role, User


def user_to_domain(row: UserTable) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        full_name=row.full_name,
        role=Role(row.role),
        is_active=row.is_active,
        created_at=row.created_at,
    )


def user_to_table(user: User) -> UserTable:
    return UserTable(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def speaker_to_domain(row: SpeakerTable) -> Speaker:
    return Speaker(
        id=row.id,
        name=row.name,
        email=row.email,
        bio=row.bio,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
    )


def speaker_to_table(speaker: Speaker) -> SpeakerTable:
    return SpeakerTable(
        id=speaker.id,
        name=speaker.name,
        email=speaker.email,
        bio=speaker.bio,
        created_by_id=speaker.created_by_id,
        created_at=speaker.created_at,
    )


def event_to_domain(row: EventTable) -> Event:
    return Event(
        id=row.id,
        name=row.name,
        description=row.description,
        location=row.location,
        start_at=row.start_at,
        end_at=row.end_at,
        capacity=row.capacity,
        registered_count=row.registered_count,
        status=EventStatus(row.status),
        organizer_id=row.organizer_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
        closed_by_id=row.closed_by_id,
        closed_source=ClosedSource(row.closed_source) if row.closed_source else None,
    )


def apply_event_to_row(event: Event, row: EventTable) -> None:
    """Copia los campos mutables de la entidad a la fila existente."""
    row.name = event.name
    row.description = event.description
    row.location = event.location
    row.start_at = event.start_at
    row.end_at = event.end_at
    row.capacity = event.capacity
    row.registered_count = event.registered_count
    row.status = event.status.value
    row.closed_at = event.closed_at
    row.closed_by_id = event.closed_by_id
    row.closed_source = event.closed_source.value if event.closed_source else None
    row.updated_at = event.updated_at


def event_to_table(event: Event) -> EventTable:
    return EventTable(
        id=event.id,
        name=event.name,
        description=event.description,
        location=event.location,
        start_at=event.start_at,
        end_at=event.end_at,
        capacity=event.capacity,
        registered_count=event.registered_count,
        status=event.status.value,
        organizer_id=event.organizer_id,
        closed_at=event.closed_at,
        closed_by_id=event.closed_by_id,
        closed_source=event.closed_source.value if event.closed_source else None,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )

"""Constructores de entidades para los tests."""

from datetime import timedelta
from uuid import UUID, uuid4

from app.domain.models.event import Event, EventStatus
from app.domain.models.speaker import Speaker
from app.domain.models.user import Role, User
from tests.fakes.in_memory import FIXED_NOW


def make_user(role: Role = Role.ATTENDEE, *, email: str | None = None, active: bool = True) -> User:
    user = User.new(
        email=email or f"{role.value}-{uuid4().hex[:6]}@example.com",
        password_hash="hashed:secreto123",
        full_name=role.value.title(),
        now=FIXED_NOW,
        role=role,
    )
    user.is_active = active
    return user


def make_event(
    organizer_id: UUID,
    *,
    name: str = "Congreso de Tecnología",
    status: EventStatus = EventStatus.DRAFT,
    capacity: int = 100,
    registered: int = 0,
    starts_in: timedelta = timedelta(days=10),
    lasts: timedelta = timedelta(hours=8),
) -> Event:
    event = Event.new(
        name=name,
        description="Descripción",
        location="Bogotá",
        start_at=FIXED_NOW + starts_in,
        end_at=FIXED_NOW + starts_in + lasts,
        capacity=capacity,
        organizer_id=organizer_id,
        now=FIXED_NOW,
    )
    event.status = status
    event.registered_count = registered
    return event


def make_speaker(created_by_id: UUID, name: str = "Ana Ponente") -> Speaker:
    return Speaker.new(
        name=name, email="ana@ponentes.co", bio="Bio", created_by_id=created_by_id, now=FIXED_NOW
    )

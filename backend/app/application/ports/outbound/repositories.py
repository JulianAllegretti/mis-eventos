from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.dto.queries import EventSearchCriteria
from app.domain.models.event import Event
from app.domain.models.registration import Registration, SessionRegistration
from app.domain.models.session import Session
from app.domain.models.speaker import Speaker
from app.domain.models.user import User


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, user: User) -> None:
        """Persiste el usuario. Lanza EmailAlreadyRegistered si el correo ya existe."""
        ...

    async def update(self, user: User) -> None: ...

    async def list_page(self, q: str | None, limit: int, offset: int) -> tuple[list[User], int]:
        """Usuarios filtrados por correo o nombre (coincidencia parcial) y su total."""
        ...


class EventRepository(Protocol):
    async def get(self, event_id: UUID) -> Event | None: ...

    async def add(self, event: Event) -> None: ...

    async def update(self, event: Event) -> None: ...

    async def delete(self, event_id: UUID) -> None: ...

    async def search(self, criteria: EventSearchCriteria) -> tuple[list[Event], int]:
        """Eventos que cumplen el criterio, ordenados por inicio, y el total sin paginar."""
        ...

    async def try_increment_registered(self, event_id: UUID, now: datetime) -> bool:
        """Toma un cupo con una sola sentencia atómica. False si está lleno o no admite altas."""
        ...

    async def decrement_registered(self, event_id: UUID) -> None: ...

    async def finish_expired(self, now: datetime) -> list[UUID]:
        """Pasa a finished los eventos publicados cuya fecha fin ya pasó (cierre automático)."""
        ...

    async def list_open_availability(self, now: datetime) -> list[tuple[UUID, int]]:
        """(id, cupos disponibles) de los eventos publicados que no han terminado."""
        ...


class SpeakerRepository(Protocol):
    async def get(self, speaker_id: UUID) -> Speaker | None: ...

    async def get_many(self, speaker_ids: list[UUID]) -> list[Speaker]: ...

    async def add(self, speaker: Speaker) -> None: ...

    async def update(self, speaker: Speaker) -> None: ...

    async def delete(self, speaker_id: UUID) -> None: ...

    async def list_page(
        self, q: str | None, limit: int, offset: int
    ) -> tuple[list[Speaker], int]: ...


class SessionRepository(Protocol):
    async def get(self, session_id: UUID) -> Session | None: ...

    async def add(self, session: Session) -> None:
        """Lanza ScheduleConflict si el ponente ya tiene una sesión en ese horario."""
        ...

    async def update(self, session: Session) -> None:
        """Lanza ScheduleConflict si el ponente ya tiene una sesión en ese horario."""
        ...

    async def delete(self, session_id: UUID) -> None: ...

    async def list_for_event(self, event_id: UUID) -> list[Session]: ...

    async def count_for_speaker(self, speaker_id: UUID) -> int: ...

    async def speaker_has_overlap(
        self, speaker_id: UUID, start_at: datetime, end_at: datetime, exclude_id: UUID | None
    ) -> bool: ...

    async def try_increment_registered(self, session_id: UUID) -> bool: ...

    async def decrement_registered(self, session_id: UUID) -> None: ...


class RegistrationRepository(Protocol):
    async def get_active(self, user_id: UUID, event_id: UUID) -> Registration | None: ...

    async def add(self, registration: Registration) -> None:
        """Lanza AlreadyRegistered si el usuario ya tiene una inscripción activa al evento."""
        ...

    async def cancel(self, user_id: UUID, event_id: UUID, now: datetime) -> bool:
        """Marca la inscripción activa como cancelada. False si no había ninguna."""
        ...

    async def exists_for_event(self, event_id: UUID) -> bool:
        """Hay inscripciones (activas o canceladas) al evento."""
        ...

    async def list_active_for_user(self, user_id: UUID) -> list[tuple[Registration, Event]]: ...

    async def list_attendees(
        self, event_id: UUID, limit: int, offset: int
    ) -> tuple[list[tuple[Registration, User]], int]: ...


class SessionRegistrationRepository(Protocol):
    async def lock_user(self, user_id: UUID) -> None:
        """Serializa las inscripciones a sesiones del mismo usuario dentro de la transacción."""
        ...

    async def get_active(self, user_id: UUID, session_id: UUID) -> SessionRegistration | None: ...

    async def add(self, registration: SessionRegistration) -> None:
        """Lanza AlreadyRegistered si ya hay una inscripción activa a la sesión."""
        ...

    async def cancel(self, user_id: UUID, session_id: UUID, now: datetime) -> bool: ...

    async def cancel_all_for_event(
        self, user_id: UUID, event_id: UUID, now: datetime
    ) -> list[UUID]:
        """Cancela las inscripciones activas del usuario a sesiones del evento; devuelve sus ids."""
        ...

    async def has_overlap(self, user_id: UUID, start_at: datetime, end_at: datetime) -> bool: ...

    async def list_active_for_user(
        self, user_id: UUID
    ) -> list[tuple[SessionRegistration, Session]]: ...

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.domain.errors import InvalidTransition, ValidationFailed
from app.domain.models.event import Event, EventStatus
from app.domain.models.session import Session

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000


@dataclass(frozen=True, slots=True)
class SessionData:
    speaker_id: UUID
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    capacity: int


def validate_session_data(data: SessionData, event: Event, *, min_capacity: int = 1) -> SessionData:
    """Valida una sesión contra su evento: horario dentro del evento y capacidad ≤ la del evento."""
    problems: list[str] = []

    title = data.title.strip()
    if not title or len(title) > TITLE_MAX_LENGTH:
        problems.append(f"title: debe tener entre 1 y {TITLE_MAX_LENGTH} caracteres")

    description = data.description.strip() if data.description else None
    if description and len(description) > DESCRIPTION_MAX_LENGTH:
        problems.append(f"description: máximo {DESCRIPTION_MAX_LENGTH} caracteres")

    if data.start_at.tzinfo is None or data.end_at.tzinfo is None:
        problems.append("start_at/end_at: deben incluir zona horaria")
    else:
        if data.end_at <= data.start_at:
            problems.append("end_at: debe ser posterior a start_at")
        if data.start_at < event.start_at or data.end_at > event.end_at:
            problems.append("start_at/end_at: la sesión debe estar dentro del horario del evento")

    if not min_capacity <= data.capacity <= event.capacity:
        if min_capacity > 1:
            problems.append(
                f"capacity: debe estar entre los inscritos actuales ({min_capacity}) "
                f"y la capacidad del evento ({event.capacity})"
            )
        else:
            problems.append(
                f"capacity: debe estar entre 1 y la capacidad del evento ({event.capacity})"
            )

    if problems:
        raise ValidationFailed("Datos de sesión inválidos", problems)
    return replace(data, title=title, description=description or None)


def validate_sessions_fit_event(
    sessions: list[Session], *, start_at: datetime, end_at: datetime, capacity: int
) -> None:
    """Al editar un evento, sus sesiones deben seguir cabiendo en el nuevo horario y capacidad."""
    problems: list[str] = []
    if any(s.start_at < start_at or s.end_at > end_at for s in sessions):
        problems.append("start_at/end_at: hay sesiones fuera del nuevo horario del evento")
    if any(s.capacity > capacity for s in sessions):
        problems.append("capacity: hay sesiones con más capacidad que el evento")
    if problems:
        raise ValidationFailed("El cambio deja sesiones inconsistentes", problems)


def ensure_registrable(event: Event, now: datetime) -> None:
    """Inscripciones y cancelaciones solo en eventos publicados que no han terminado."""
    if event.effective_status(now) is not EventStatus.PUBLISHED:
        raise InvalidTransition("El evento no admite inscripciones")

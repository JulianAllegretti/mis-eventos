from dataclasses import dataclass, replace
from datetime import datetime

from app.domain.errors import ValidationFailed

NAME_MAX_LENGTH = 200
LOCATION_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 5000
CAPACITY_MAX = 100_000


@dataclass(frozen=True, slots=True)
class EventData:
    name: str
    description: str | None
    location: str
    start_at: datetime
    end_at: datetime
    capacity: int


def validate_event_data(
    data: EventData,
    *,
    now: datetime,
    require_future_start: bool,
    min_capacity: int = 1,
) -> EventData:
    """Valida y limpia los datos de un evento. Reúne todos los problemas en un solo error."""
    problems: list[str] = []

    name = data.name.strip()
    if not name or len(name) > NAME_MAX_LENGTH:
        problems.append(f"name: debe tener entre 1 y {NAME_MAX_LENGTH} caracteres")

    location = data.location.strip()
    if not location or len(location) > LOCATION_MAX_LENGTH:
        problems.append(f"location: debe tener entre 1 y {LOCATION_MAX_LENGTH} caracteres")

    description = data.description.strip() if data.description else None
    if description and len(description) > DESCRIPTION_MAX_LENGTH:
        problems.append(f"description: máximo {DESCRIPTION_MAX_LENGTH} caracteres")

    if data.start_at.tzinfo is None or data.end_at.tzinfo is None:
        problems.append("start_at/end_at: deben incluir zona horaria")
    else:
        if data.end_at <= data.start_at:
            problems.append("end_at: debe ser posterior a start_at")
        if require_future_start and data.start_at <= now:
            problems.append("start_at: debe estar en el futuro")

    if not min_capacity <= data.capacity <= CAPACITY_MAX:
        if min_capacity > 1:
            problems.append(
                f"capacity: no puede ser menor que los inscritos actuales ({min_capacity})"
            )
        else:
            problems.append(f"capacity: debe estar entre 1 y {CAPACITY_MAX}")

    if problems:
        raise ValidationFailed("Datos de evento inválidos", problems)
    return replace(data, name=name, location=location, description=description or None)

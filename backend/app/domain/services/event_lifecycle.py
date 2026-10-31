"""Máquina de estados del evento: draft → published → finished; draft|published → cancelled."""

from datetime import datetime
from uuid import UUID

from app.domain.errors import InvalidTransition, ValidationFailed
from app.domain.models.event import ClosedSource, Event, EventStatus

_EDITABLE = (EventStatus.DRAFT, EventStatus.PUBLISHED)


def ensure_editable(event: Event, now: datetime) -> None:
    if event.effective_status(now) not in _EDITABLE:
        raise InvalidTransition("Un evento finalizado o cancelado no se puede modificar")


def publish(event: Event, now: datetime) -> None:
    if event.effective_status(now) is not EventStatus.DRAFT:
        raise InvalidTransition("Solo un borrador se puede publicar")
    if event.start_at <= now:
        raise ValidationFailed("No se puede publicar un evento cuyo inicio ya pasó")
    event.status = EventStatus.PUBLISHED
    event.updated_at = now


def finish(event: Event, actor_id: UUID, now: datetime) -> None:
    if event.effective_status(now) is not EventStatus.PUBLISHED:
        raise InvalidTransition("Solo un evento publicado y en curso se puede finalizar")
    _close(event, EventStatus.FINISHED, actor_id, now)


def cancel(event: Event, actor_id: UUID, now: datetime) -> None:
    if event.effective_status(now) not in _EDITABLE:
        raise InvalidTransition("Solo un borrador o un evento publicado se puede cancelar")
    _close(event, EventStatus.CANCELLED, actor_id, now)


def _close(event: Event, status: EventStatus, actor_id: UUID, now: datetime) -> None:
    event.status = status
    event.closed_at = now
    event.closed_by_id = actor_id
    event.closed_source = ClosedSource.MANUAL
    event.updated_at = now

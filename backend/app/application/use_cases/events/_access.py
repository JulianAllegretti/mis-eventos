from uuid import UUID

from app.application.ports.outbound.unit_of_work import UnitOfWork
from app.domain.errors import NotFound
from app.domain.models.event import Event
from app.domain.models.user import User
from app.domain.services.permissions import can_view_event, ensure_can_manage_event


async def load_visible_event(uow: UnitOfWork, event_id: UUID, viewer: User | None) -> Event:
    """Carga un evento. Un borrador ajeno responde igual que uno inexistente (404)."""
    event = await uow.events.get(event_id)
    if event is None or not can_view_event(viewer, event):
        raise NotFound("Evento no encontrado")
    return event


async def load_managed_event(uow: UnitOfWork, event_id: UUID, actor: User) -> Event:
    """Carga un evento que el actor puede ver y, además, administrar."""
    event = await load_visible_event(uow, event_id, actor)
    ensure_can_manage_event(actor, event)
    return event

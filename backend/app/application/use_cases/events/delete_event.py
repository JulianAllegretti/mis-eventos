from app.application.dto.commands import EventActionCommand
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.services.event_sync import EventSync
from app.application.use_cases.events._access import load_managed_event
from app.domain.errors import Conflict


class DeleteEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, sync: EventSync) -> None:
        self._uow_factory = uow_factory
        self._sync = sync

    async def execute(self, cmd: EventActionCommand) -> None:
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            if event.registered_count > 0 or await uow.registrations.exists_for_event(event.id):
                raise Conflict("El evento tiene inscripciones: cancélalo en lugar de borrarlo")
            await uow.events.delete(event.id)  # sus sesiones se borran en cascada
            await uow.commit()
        await self._sync.event_changed(cmd.event_id)

from app.application.dto.commands import EventActionCommand
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.events._access import load_managed_event
from app.domain.errors import Conflict


class DeleteEventUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, cmd: EventActionCommand) -> None:
        async with self._uow_factory() as uow:
            event = await load_managed_event(uow, cmd.event_id, cmd.actor)
            if event.registered_count > 0:
                raise Conflict("El evento tiene inscripciones: cancélalo en lugar de borrarlo")
            await uow.events.delete(event.id)
            await uow.commit()

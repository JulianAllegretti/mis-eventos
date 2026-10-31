from app.application.dto.commands import UpdateUserCommand
from app.application.dto.paging import resolve_page
from app.application.dto.queries import ListUsersQuery
from app.application.dto.read_models import Page
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import Forbidden, NotFound, ValidationFailed
from app.domain.models.user import Role, User
from app.domain.services.permissions import ensure_role

_UPDATABLE = frozenset({"role", "is_active"})


class ListUsersUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListUsersQuery) -> Page[User]:
        ensure_role(query.actor, Role.ADMIN)
        page, limit, offset = resolve_page(query.page, query.page_size)
        q = query.q.strip() if query.q else None
        async with self._uow_factory() as uow:
            items, total = await uow.users.list_page(q or None, limit, offset)
        return Page(items=items, total=total, page=page, page_size=query.page_size)


class UpdateUserUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, cmd: UpdateUserCommand) -> User:
        ensure_role(cmd.actor, Role.ADMIN)
        unknown = set(cmd.changes) - _UPDATABLE
        if unknown or not cmd.changes:
            raise ValidationFailed("Solo se pueden cambiar role e is_active", sorted(unknown))
        if cmd.user_id == cmd.actor.id:
            # Evita que el último administrador se bloquee a sí mismo.
            raise Forbidden("No puedes cambiar tu propio rol ni desactivarte")

        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(cmd.user_id)
            if user is None:
                raise NotFound("Usuario no encontrado")
            if "role" in cmd.changes:
                try:
                    user.role = Role(cmd.changes["role"])
                except ValueError as exc:
                    raise ValidationFailed("role inválido") from exc
            if "is_active" in cmd.changes:
                if not isinstance(cmd.changes["is_active"], bool):
                    raise ValidationFailed("is_active debe ser booleano")
                user.is_active = cmd.changes["is_active"]
            await uow.users.update(user)
            await uow.commit()
        return user

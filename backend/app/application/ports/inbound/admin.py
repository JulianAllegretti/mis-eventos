from typing import Protocol

from app.application.dto.commands import UpdateUserCommand
from app.application.dto.queries import ListUsersQuery
from app.application.dto.read_models import Page
from app.domain.models.user import User


class EnsureAdminUser(Protocol):
    async def execute(self, email: str, password: str) -> bool:
        """Crea el administrador inicial si no existe. Devuelve True si lo creó."""
        ...


class ListUsers(Protocol):
    async def execute(self, query: ListUsersQuery) -> Page[User]: ...


class UpdateUser(Protocol):
    async def execute(self, cmd: UpdateUserCommand) -> User: ...

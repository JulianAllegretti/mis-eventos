from typing import Protocol

from app.application.dto.commands import LoginCommand, RegisterUserCommand
from app.application.dto.read_models import AuthResult
from app.domain.models.user import User


class RegisterUser(Protocol):
    async def execute(self, cmd: RegisterUserCommand) -> User: ...


class LoginUser(Protocol):
    async def execute(self, cmd: LoginCommand) -> AuthResult: ...


class GetCurrentUser(Protocol):
    async def execute(self, token: str | None) -> User:
        """Resuelve el usuario de un token. Lanza NotAuthenticated si no es válido."""
        ...

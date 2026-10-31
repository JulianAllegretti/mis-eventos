from app.application.dto.commands import LoginCommand
from app.application.dto.read_models import AuthResult
from app.application.ports.outbound.security import PasswordHasher, TokenService
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import InvalidCredentials, ValidationFailed
from app.domain.services.credentials import normalize_email


class LoginUserUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, hasher: PasswordHasher, tokens: TokenService
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._tokens = tokens

    async def execute(self, cmd: LoginCommand) -> AuthResult:
        try:
            email = normalize_email(cmd.email)
        except ValidationFailed as exc:
            raise InvalidCredentials() from exc

        async with self._uow_factory() as uow:
            user = await uow.users.get_by_email(email)

        if user is None:
            # Gasta un tiempo similar al de verificar, para no revelar si el correo existe.
            await self._hasher.hash(cmd.password)
            raise InvalidCredentials()
        if not await self._hasher.verify(cmd.password, user.password_hash) or not user.is_active:
            raise InvalidCredentials()

        return AuthResult(
            user=user, token=self._tokens.issue(user), expires_in=self._tokens.ttl_seconds
        )

from app.application.dto.commands import RegisterUserCommand
from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.security import PasswordHasher
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import EmailAlreadyRegistered
from app.domain.models.user import User
from app.domain.services.credentials import (
    normalize_email,
    validate_full_name,
    validate_password,
)


class RegisterUserUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, hasher: PasswordHasher, clock: Clock
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._clock = clock

    async def execute(self, cmd: RegisterUserCommand) -> User:
        email = normalize_email(cmd.email)
        full_name = validate_full_name(cmd.full_name)
        validate_password(cmd.password)

        user = User.new(
            email=email,
            password_hash=await self._hasher.hash(cmd.password),
            full_name=full_name,
            now=self._clock.now(),
        )
        async with self._uow_factory() as uow:
            if await uow.users.get_by_email(email) is not None:
                raise EmailAlreadyRegistered()
            await uow.users.add(user)
            await uow.commit()
        return user

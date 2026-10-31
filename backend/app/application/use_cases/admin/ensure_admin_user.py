from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.security import PasswordHasher
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.models.user import Role, User
from app.domain.services.credentials import normalize_email, validate_password


class EnsureAdminUserUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, hasher: PasswordHasher, clock: Clock
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._clock = clock

    async def execute(self, email: str, password: str) -> bool:
        email = normalize_email(email)
        validate_password(password)
        async with self._uow_factory() as uow:
            if await uow.users.get_by_email(email) is not None:
                return False
            admin = User.new(
                email=email,
                password_hash=await self._hasher.hash(password),
                full_name="Administrador",
                now=self._clock.now(),
                role=Role.ADMIN,
            )
            await uow.users.add(admin)
            await uow.commit()
        return True

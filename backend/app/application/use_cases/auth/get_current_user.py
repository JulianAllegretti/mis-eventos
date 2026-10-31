from app.application.ports.outbound.security import TokenService
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import NotAuthenticated
from app.domain.models.user import User


class GetCurrentUserUseCase:
    """Resuelve el usuario desde la BD en cada petición para que rol e is_active estén al día."""

    def __init__(self, uow_factory: UnitOfWorkFactory, tokens: TokenService) -> None:
        self._uow_factory = uow_factory
        self._tokens = tokens

    async def execute(self, token: str | None) -> User:
        claims = self._tokens.decode(token) if token else None
        if claims is None:
            raise NotAuthenticated()
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise NotAuthenticated()
        return user

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.models.user import Role, User


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: UUID
    role: Role


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    @property
    def ttl_seconds(self) -> int: ...

    def issue(self, user: User) -> str: ...

    def decode(self, token: str) -> TokenClaims | None:
        """Devuelve los claims si el token es válido y no ha expirado; si no, None."""
        ...

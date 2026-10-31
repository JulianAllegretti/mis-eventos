from typing import Protocol
from uuid import UUID

from app.application.dto.queries import EventSearchCriteria
from app.domain.models.event import Event
from app.domain.models.speaker import Speaker
from app.domain.models.user import User


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def add(self, user: User) -> None:
        """Persiste el usuario. Lanza EmailAlreadyRegistered si el correo ya existe."""
        ...

    async def update(self, user: User) -> None: ...

    async def list_page(self, q: str | None, limit: int, offset: int) -> tuple[list[User], int]:
        """Usuarios filtrados por correo o nombre (coincidencia parcial) y su total."""
        ...


class EventRepository(Protocol):
    async def get(self, event_id: UUID) -> Event | None: ...

    async def add(self, event: Event) -> None: ...

    async def update(self, event: Event) -> None: ...

    async def delete(self, event_id: UUID) -> None: ...

    async def search(self, criteria: EventSearchCriteria) -> tuple[list[Event], int]:
        """Eventos que cumplen el criterio, ordenados por inicio, y el total sin paginar."""
        ...


class SpeakerRepository(Protocol):
    async def get(self, speaker_id: UUID) -> Speaker | None: ...

    async def add(self, speaker: Speaker) -> None: ...

    async def update(self, speaker: Speaker) -> None: ...

    async def delete(self, speaker_id: UUID) -> None: ...

    async def list_page(
        self, q: str | None, limit: int, offset: int
    ) -> tuple[list[Speaker], int]: ...

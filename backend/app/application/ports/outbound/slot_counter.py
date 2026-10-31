from enum import StrEnum
from typing import Protocol
from uuid import UUID


class SlotResult(StrEnum):
    ALLOWED = "allowed"  # se descontó un cupo del contador
    FULL = "full"  # el contador está en cero: se rechaza sin tocar PostgreSQL
    MISSING = "missing"  # el contador aún no existe: hay que inicializarlo desde PostgreSQL
    BYPASSED = "bypassed"  # el contador no está disponible: decide solo PostgreSQL


class SlotCounter(Protocol):
    """Filtro previo de cupos (ADR 0005). Nunca es la autoridad: PostgreSQL decide al final."""

    async def claim(self, event_id: UUID, user_id: UUID) -> bool:
        """Candado corto por (evento, usuario): colapsa los clics dobles antes de reservar cupo.

        Sin él, los intentos duplicados retienen cupo mientras están en vuelo y el contador puede
        rechazar a usuarios legítimos con "evento lleno" aunque quede lugar. False = ya hay un
        intento en curso o reciente de este usuario.
        """
        ...

    async def unclaim(self, event_id: UUID, user_id: UUID) -> None: ...

    async def try_acquire(self, event_id: UUID) -> SlotResult: ...

    async def release(self, event_id: UUID) -> None:
        """Devuelve un cupo si el contador existe (compensación)."""
        ...

    async def initialize(self, event_id: UUID, available: int) -> None:
        """Crea el contador solo si no existe."""
        ...

    async def reconcile(self, event_id: UUID, available: int) -> None:
        """Corrige el contador con el valor real de PostgreSQL, solo si ya existe."""
        ...

    async def invalidate(self, event_id: UUID) -> None:
        """Borra el contador; se reconstruirá desde PostgreSQL en la próxima inscripción."""
        ...

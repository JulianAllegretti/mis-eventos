from typing import Protocol
from uuid import UUID


class FinishExpiredEvents(Protocol):
    async def execute(self) -> list[UUID]:
        """Cierra los eventos vencidos y devuelve los ids cerrados (ADR 0008)."""
        ...


class ReconcileSlots(Protocol):
    async def execute(self) -> int:
        """Corrige los contadores de cupos desde PostgreSQL; devuelve cuántos eventos revisó."""
        ...

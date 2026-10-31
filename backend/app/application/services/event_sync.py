from uuid import UUID

from app.application.ports.outbound.cache import Cache
from app.application.ports.outbound.slot_counter import SlotCounter

EVENTS_CACHE_GROUP = "events"


class EventSync:
    """Mantiene coherentes los derivados de PostgreSQL (caché y contador de cupos) tras escribir."""

    def __init__(self, cache: Cache, slots: SlotCounter) -> None:
        self._cache = cache
        self._slots = slots

    async def event_changed(self, event_id: UUID) -> None:
        """Cambió el evento (datos, capacidad o estado): el contador se reconstruye bajo demanda."""
        await self._slots.invalidate(event_id)
        await self._cache.invalidate_group(EVENTS_CACHE_GROUP)

    async def counts_changed(self) -> None:
        """Cambiaron cupos, sesiones o inscripciones: solo la caché de lectura queda vieja."""
        await self._cache.invalidate_group(EVENTS_CACHE_GROUP)

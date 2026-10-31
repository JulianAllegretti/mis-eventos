from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CacheLookup:
    """Resultado de una lectura. `version` es la del grupo en ese momento: si el grupo se invalida
    entre la lectura y la escritura, el valor calculado con datos viejos no se publica."""

    value: str | None
    version: str


class Cache(Protocol):
    async def get(self, group: str, key: str) -> CacheLookup: ...

    async def set(
        self, group: str, key: str, version: str, value: str, ttl_seconds: int
    ) -> None: ...

    async def invalidate_group(self, group: str) -> None: ...

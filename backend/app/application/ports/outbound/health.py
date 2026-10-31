from typing import Protocol


class HealthProbe(Protocol):
    name: str
    critical: bool

    async def check(self) -> bool: ...

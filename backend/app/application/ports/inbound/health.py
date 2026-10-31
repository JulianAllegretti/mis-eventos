from typing import Protocol

from app.application.dto.read_models import ReadinessReport


class CheckReadiness(Protocol):
    async def execute(self) -> ReadinessReport: ...

import asyncio

from app.application.dto.read_models import ReadinessReport
from app.application.ports.outbound.health import HealthProbe

PROBE_TIMEOUT_SECONDS = 2.0


class CheckReadinessUseCase:
    def __init__(self, probes: list[HealthProbe]) -> None:
        self._probes = probes

    async def execute(self) -> ReadinessReport:
        results = await asyncio.gather(*(self._run(probe) for probe in self._probes))
        checks = {probe.name: ok for probe, ok in zip(self._probes, results, strict=True)}
        if any(not ok for probe, ok in zip(self._probes, results, strict=True) if probe.critical):
            return ReadinessReport(status="unavailable", checks=checks)
        if not all(results):
            return ReadinessReport(status="degraded", checks=checks)
        return ReadinessReport(status="ok", checks=checks)

    @staticmethod
    async def _run(probe: HealthProbe) -> bool:
        try:
            return await asyncio.wait_for(probe.check(), timeout=PROBE_TIMEOUT_SECONDS)
        except Exception:
            return False

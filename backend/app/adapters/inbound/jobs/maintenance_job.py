import asyncio
import contextlib

import structlog

from app.application.ports.inbound.maintenance import FinishExpiredEvents, ReconcileSlots
from app.application.ports.outbound.metrics import Metrics

log = structlog.get_logger()


class MaintenanceJob:
    """Tarea periódica: cierra eventos vencidos (ADR 0008) y corrige contadores de cupos (ADR 0005).

    `run_once` es invocable directamente, así los tests no esperan al temporizador.
    """

    def __init__(
        self,
        finish_expired: FinishExpiredEvents,
        reconcile_slots: ReconcileSlots,
        interval_seconds: float,
        metrics: Metrics,
    ) -> None:
        self._finish_expired = finish_expired
        self._reconcile_slots = reconcile_slots
        self._interval = interval_seconds
        self._metrics = metrics
        self._task: asyncio.Task[None] | None = None

    async def run_once(self) -> None:
        # Un fallo se registra y se reintenta en el siguiente ciclo; nunca detiene la aplicación.
        try:
            closed = await self._finish_expired.execute()
            if closed:
                log.info("events_closed", count=len(closed), source="scheduler")
            self._metrics.maintenance_run("finish_expired", ok=True)
        except Exception:
            log.exception("finish_expired_failed")
            self._metrics.maintenance_run("finish_expired", ok=False)
        try:
            await self._reconcile_slots.execute()
            self._metrics.maintenance_run("reconcile_slots", ok=True)
        except Exception:
            log.exception("reconcile_slots_failed")
            self._metrics.maintenance_run("reconcile_slots", ok=False)

    def start(self) -> None:
        if self._task is None and self._interval > 0:
            self._task = asyncio.create_task(self._loop(), name="maintenance-job")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self._interval)

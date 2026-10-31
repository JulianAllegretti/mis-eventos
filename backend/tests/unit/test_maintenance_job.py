import asyncio
from uuid import uuid4

from app.adapters.inbound.jobs.maintenance_job import MaintenanceJob


class _Finish:
    def __init__(self, result=None, error=None):
        self.calls, self._result, self._error = 0, result or [], error

    async def execute(self):
        self.calls += 1
        if self._error:
            raise self._error
        return self._result


class _Reconcile:
    def __init__(self, error=None):
        self.calls, self._error = 0, error

    async def execute(self):
        self.calls += 1
        if self._error:
            raise self._error
        return 0


async def test_run_once_executes_both_tasks():
    finish, reconcile = _Finish([uuid4()]), _Reconcile()
    await MaintenanceJob(finish, reconcile, interval_seconds=60).run_once()
    assert (finish.calls, reconcile.calls) == (1, 1)


async def test_a_failure_in_one_task_does_not_stop_the_other():
    finish, reconcile = _Finish(error=RuntimeError("PostgreSQL caído")), _Reconcile()
    await MaintenanceJob(finish, reconcile, interval_seconds=60).run_once()  # no lanza
    assert reconcile.calls == 1

    finish, reconcile = _Finish(), _Reconcile(error=RuntimeError("Redis caído"))
    await MaintenanceJob(finish, reconcile, interval_seconds=60).run_once()
    assert finish.calls == 1


async def test_the_loop_repeats_and_stops_cleanly():
    finish, reconcile = _Finish(), _Reconcile()
    job = MaintenanceJob(finish, reconcile, interval_seconds=0.01)

    job.start()
    job.start()  # idempotente: no crea una segunda tarea
    await asyncio.sleep(0.1)
    await job.stop()
    calls_at_stop = finish.calls
    await asyncio.sleep(0.05)

    assert calls_at_stop >= 3
    assert finish.calls == calls_at_stop  # ya no corre tras detenerlo


async def test_interval_zero_disables_the_loop():
    finish = _Finish()
    job = MaintenanceJob(finish, _Reconcile(), interval_seconds=0)
    job.start()
    await asyncio.sleep(0.05)
    await job.stop()
    assert finish.calls == 0

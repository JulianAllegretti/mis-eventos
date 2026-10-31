from app.application.use_cases.health.check_readiness import CheckReadinessUseCase
from tests.fakes.in_memory import StaticProbe


async def test_ok_when_everything_is_up():
    report = await CheckReadinessUseCase(
        [StaticProbe("postgres", True, True), StaticProbe("redis", True, False)]
    ).execute()
    assert report.status == "ok"
    assert report.checks == {"postgres": True, "redis": True}


async def test_degraded_when_only_non_critical_fails():
    report = await CheckReadinessUseCase(
        [StaticProbe("postgres", True, True), StaticProbe("redis", False, False)]
    ).execute()
    assert report.status == "degraded"


async def test_unavailable_when_critical_fails():
    report = await CheckReadinessUseCase(
        [StaticProbe("postgres", False, True), StaticProbe("redis", True, False)]
    ).execute()
    assert report.status == "unavailable"


async def test_probe_that_raises_counts_as_failed():
    class Exploding:
        name = "postgres"
        critical = True

        async def check(self) -> bool:
            raise ConnectionError("sin conexión")

    report = await CheckReadinessUseCase([Exploding()]).execute()
    assert report.status == "unavailable"
    assert report.checks == {"postgres": False}

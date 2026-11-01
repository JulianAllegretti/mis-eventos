import time

from prometheus_client import CollectorRegistry, Counter, Gauge
from prometheus_client.gc_collector import GCCollector
from prometheus_client.platform_collector import PlatformCollector
from prometheus_client.process_collector import ProcessCollector

NAMESPACE = "miseventos"


def create_registry() -> CollectorRegistry:
    """Registro propio (no el global) con las métricas del proceso de Python."""
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    PlatformCollector(registry=registry)
    GCCollector(registry=registry)
    return registry


class PrometheusMetrics:
    """Implementa el puerto Metrics. Cada etiqueta toma valores de un conjunto cerrado."""

    def __init__(self, registry: CollectorRegistry) -> None:
        def counter(name: str, doc: str, labels: tuple[str, ...] = ()) -> Counter:
            return Counter(name, doc, labels, namespace=NAMESPACE, registry=registry)

        self._registrations = counter(
            "registrations_total", "Intentos de inscripción a eventos por resultado.", ("result",)
        )
        self._slot_filter = counter(
            "slot_filter_total", "Decisiones del filtro de cupos de Redis.", ("result",)
        )
        self._compensations = counter(
            "slot_compensations_total", "Cupos devueltos a Redis tras un rechazo de PostgreSQL."
        )
        self._events_closed = counter(
            "events_closed_total", "Eventos cerrados por origen.", ("source",)
        )
        self._maintenance = counter(
            "maintenance_runs_total", "Ejecuciones de la tarea periódica.", ("task", "result")
        )
        self._maintenance_last_ok = Gauge(
            "maintenance_last_success_timestamp_seconds",
            "Instante de la última ejecución correcta de cada tarea periódica.",
            ("task",),
            namespace=NAMESPACE,
            registry=registry,
        )
        self._logins = counter(
            "login_attempts_total", "Intentos de login por resultado.", ("result",)
        )
        self._cache = counter(
            "cache_lookups_total", "Lecturas de la caché de eventos.", ("kind", "result")
        )

    def registration_attempt(self, result: str) -> None:
        self._registrations.labels(result).inc()

    def slot_filter(self, result: str) -> None:
        self._slot_filter.labels(result).inc()

    def slot_compensation(self) -> None:
        self._compensations.inc()

    def event_closed(self, source: str, count: int = 1) -> None:
        self._events_closed.labels(source).inc(count)

    def maintenance_run(self, task: str, ok: bool) -> None:
        self._maintenance.labels(task, "ok" if ok else "error").inc()
        if ok:
            self._maintenance_last_ok.labels(task).set(time.time())

    def login_attempt(self, result: str) -> None:
        self._logins.labels(result).inc()

    def cache_lookup(self, kind: str, hit: bool) -> None:
        self._cache.labels(kind, "hit" if hit else "miss").inc()

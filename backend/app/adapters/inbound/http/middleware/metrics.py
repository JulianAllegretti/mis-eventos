import time
from collections.abc import Awaitable, Callable

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.adapters.inbound.http.middleware.route_template import route_template

_IGNORED_PATHS = frozenset({"/metrics"})
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Peticiones, latencia y peticiones en curso.

    La etiqueta `route` es la plantilla de la ruta (`/events/{event_id}`), nunca la URL real:
    así la cardinalidad es fija aunque haya millones de ids. Lo que no coincide con ninguna ruta
    se agrupa como `unmatched`.
    """

    def __init__(self, app: ASGIApp, registry: CollectorRegistry) -> None:
        super().__init__(app)
        self._requests = Counter(
            "http_requests_total",
            "Peticiones HTTP por método, ruta y estado.",
            ("method", "route", "status"),
            namespace="miseventos",
            registry=registry,
        )
        self._latency = Histogram(
            "http_request_duration_seconds",
            "Latencia de las peticiones HTTP.",
            ("method", "route"),
            namespace="miseventos",
            buckets=_BUCKETS,
            registry=registry,
        )
        self._in_flight = Gauge(
            "http_requests_in_flight",
            "Peticiones HTTP en curso.",
            namespace="miseventos",
            registry=registry,
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _IGNORED_PATHS:
            return await call_next(request)

        self._in_flight.inc()
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = route_template(request.scope)
            self._in_flight.dec()
            self._requests.labels(request.method, route, str(status)).inc()
            self._latency.labels(request.method, route).observe(time.perf_counter() - started)

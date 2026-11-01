import re
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.adapters.inbound.http.middleware.route_template import UNMATCHED, route_template

log = structlog.get_logger()
# Sondeos periódicos (healthchecks y scrape de Prometheus): bajan a debug para no ahogar el log.
_NOISY_PATHS = frozenset({"/health", "/health/ready", "/metrics"})
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Asigna un request_id, lo devuelve en X-Request-ID y registra cada petición en JSON."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        template = route_template(request.scope)
        emit = log.debug if request.url.path in _NOISY_PATHS else log.info
        emit(
            "http_request",
            method=request.method,
            # Plantilla de la ruta; si no coincide con ninguna, la URL real ayuda a depurar los 404.
            path=request.url.path if template == UNMATCHED else template,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=getattr(request.state, "user_id", None),
        )
        return response

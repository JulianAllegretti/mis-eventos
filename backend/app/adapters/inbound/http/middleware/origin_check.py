from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.adapters.inbound.http.cookies import SESSION_COOKIE_NAME

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Defensa CSRF: una petición que modifica datos y trae la cookie de sesión debe venir
    de un origen permitido (cabecera Origin o, si falta, Referer). Las peticiones sin cookie
    no pueden abusar de la sesión, así que no se restringen."""

    def __init__(self, app: ASGIApp, allowed_origins: tuple[str, ...]) -> None:
        super().__init__(app)
        self._allowed = frozenset(allowed_origins)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in _SAFE_METHODS and SESSION_COOKIE_NAME in request.cookies:
            origin = request.headers.get("origin") or _origin_of(request.headers.get("referer"))
            if origin not in self._allowed:
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": "origin_not_allowed",
                        "message": "Origen no permitido",
                        "details": [],
                    },
                )
        return await call_next(request)


def _origin_of(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None

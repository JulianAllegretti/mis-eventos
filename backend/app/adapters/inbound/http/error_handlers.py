from typing import cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import (
    Conflict,
    DomainError,
    Forbidden,
    NotAuthenticated,
    NotFound,
    ValidationFailed,
)

log = structlog.get_logger()

# El orden importa: se usa el primer tipo del que el error sea instancia.
_STATUS_BY_ERROR: tuple[tuple[type[DomainError], int], ...] = (
    (NotAuthenticated, 401),
    (Forbidden, 403),
    (NotFound, 404),
    (Conflict, 409),
    (ValidationFailed, 422),
)


def _body(code: str, message: str, details: list[str] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "details": details or []}


async def _handle_domain_error(_: Request, exc: Exception) -> JSONResponse:
    error = cast(DomainError, exc)  # registrado solo para DomainError
    status_code = next((s for t, s in _STATUS_BY_ERROR if isinstance(error, t)), 400)
    return JSONResponse(
        status_code=status_code, content=_body(error.code, error.message, error.details)
    )


async def _handle_request_validation(_: Request, exc: Exception) -> JSONResponse:
    error = cast(RequestValidationError, exc)
    # Solo ubicación y mensaje: el valor recibido puede ser una contraseña y no se devuelve.
    details = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in error.errors()]
    return JSONResponse(
        status_code=422, content=_body("validation_failed", "Datos inválidos", details)
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error", path=request.url.path, error=type(exc).__name__, exc_info=exc)
    return JSONResponse(status_code=500, content=_body("internal_error", "Error interno"))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
    app.add_exception_handler(Exception, _handle_unexpected)

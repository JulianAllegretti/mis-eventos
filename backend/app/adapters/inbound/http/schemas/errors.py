from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[str] = []


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Documenta en OpenAPI que estos códigos devuelven el formato estándar de error."""
    return {code: {"model": ErrorResponse} for code in status_codes}

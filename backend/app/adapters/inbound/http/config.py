from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """Parámetros que el adaptador HTTP necesita; los entrega el bootstrap."""

    cookie_secure: bool
    allowed_origins: tuple[str, ...]

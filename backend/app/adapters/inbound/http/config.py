from dataclasses import dataclass

from prometheus_client import CollectorRegistry


@dataclass(frozen=True, slots=True)
class HttpConfig:
    """Parámetros que el adaptador HTTP necesita; los entrega el bootstrap."""

    cookie_secure: bool
    allowed_origins: tuple[str, ...]
    metrics_registry: CollectorRegistry

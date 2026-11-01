from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginRateLimit:
    """Intentos de login fallidos permitidos dentro de una ventana."""

    max_failures_per_email: int = 5
    max_failures_per_ip: int = 20
    window_seconds: int = 900

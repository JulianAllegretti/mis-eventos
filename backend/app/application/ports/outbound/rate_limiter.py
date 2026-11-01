from typing import Protocol


class RateLimiter(Protocol):
    """Limita intentos fallidos por clave dentro de una ventana de tiempo.

    Si el almacenamiento no está disponible, no se bloquea a nadie (falla abierto): es una
    defensa en profundidad, no la única barrera (las contraseñas usan argon2id).
    """

    async def retry_after(self, key: str, limit: int) -> int:
        """Segundos que faltan para poder volver a intentar; 0 si no está limitada."""
        ...

    async def record_failure(self, key: str, window_seconds: int) -> None: ...

    async def reset(self, key: str) -> None: ...

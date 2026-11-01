import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

DEFAULT_MAX_CONCURRENCY = 4


class Argon2PasswordHasher:
    """argon2id con los parámetros por defecto de argon2-cffi. El cómputo corre en hilos.

    Cada hash usa 64 MiB y varios hilos a propósito (es lo que lo hace caro de atacar). Sin un
    tope, una ráfaga de altas o de intentos de login lanzaría decenas de hashes a la vez,
    agotaría memoria y CPU y degradaría al resto de la API. El semáforo los pone en cola.
    """

    def __init__(self, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        self._hasher = PasswordHasher()
        self._slots = asyncio.Semaphore(max_concurrency)

    async def hash(self, password: str) -> str:
        async with self._slots:
            return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password: str, password_hash: str) -> bool:
        async with self._slots:
            try:
                return await asyncio.to_thread(self._hasher.verify, password_hash, password)
            except (VerificationError, InvalidHashError):
                return False

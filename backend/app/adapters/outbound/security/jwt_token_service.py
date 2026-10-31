from datetime import timedelta
from uuid import UUID

import jwt

from app.application.ports.outbound.clock import Clock
from app.application.ports.outbound.security import TokenClaims
from app.domain.models.user import Role, User

ALGORITHM = "HS256"


class JwtTokenService:
    def __init__(self, secret: str, expire_minutes: int, clock: Clock) -> None:
        self._secret = secret
        self._ttl = timedelta(minutes=expire_minutes)
        self._clock = clock

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    def issue(self, user: User) -> str:
        now = self._clock.now()
        payload = {
            "sub": str(user.id),
            "role": user.role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + self._ttl).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=ALGORITHM)

    def decode(self, token: str) -> TokenClaims | None:
        try:
            # La vigencia se comprueba con el reloj inyectado (el mismo que emite el token),
            # no con la hora del sistema que usaría PyJWT.
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={"require": ["exp", "sub"], "verify_exp": False, "verify_iat": False},
            )
            if int(payload["exp"]) <= int(self._clock.now().timestamp()):
                return None
            return TokenClaims(user_id=UUID(payload["sub"]), role=Role(payload["role"]))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            return None

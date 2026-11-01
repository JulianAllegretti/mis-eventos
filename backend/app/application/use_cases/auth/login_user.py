from typing import NoReturn

from app.application.dto.commands import LoginCommand
from app.application.dto.policies import LoginRateLimit
from app.application.dto.read_models import AuthResult
from app.application.ports.outbound.metrics import Metrics
from app.application.ports.outbound.rate_limiter import RateLimiter
from app.application.ports.outbound.security import PasswordHasher, TokenService
from app.application.ports.outbound.unit_of_work import UnitOfWorkFactory
from app.domain.errors import InvalidCredentials, TooManyAttempts, ValidationFailed
from app.domain.services.credentials import normalize_email


class LoginUserUseCase:
    """Inicio de sesión con límite de intentos fallidos por correo y por origen (IP)."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: TokenService,
        limiter: RateLimiter,
        policy: LoginRateLimit,
        metrics: Metrics,
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher
        self._tokens = tokens
        self._limiter = limiter
        self._policy = policy
        self._metrics = metrics

    async def execute(self, cmd: LoginCommand) -> AuthResult:
        try:
            email = normalize_email(cmd.email)
        except ValidationFailed as exc:
            self._metrics.login_attempt("invalid")
            raise InvalidCredentials() from exc

        email_key = f"login:email:{email}"
        ip_key = f"login:ip:{cmd.client_ip}" if cmd.client_ip else None

        # Se limita por correo exista o no, para no revelar qué cuentas existen.
        wait = await self._limiter.retry_after(email_key, self._policy.max_failures_per_email)
        if ip_key:
            wait = max(
                wait, await self._limiter.retry_after(ip_key, self._policy.max_failures_per_ip)
            )
        if wait > 0:
            self._metrics.login_attempt("rate_limited")
            raise TooManyAttempts(wait)

        async with self._uow_factory() as uow:
            user = await uow.users.get_by_email(email)

        if user is None:
            # Gasta un tiempo similar al de verificar, para no revelar si el correo existe.
            await self._hasher.hash(cmd.password)
            await self._fail(email_key, ip_key)
        if not await self._hasher.verify(cmd.password, user.password_hash) or not user.is_active:
            await self._fail(email_key, ip_key)

        await self._limiter.reset(email_key)  # un acierto borra los fallos de esa cuenta
        self._metrics.login_attempt("success")
        return AuthResult(
            user=user, token=self._tokens.issue(user), expires_in=self._tokens.ttl_seconds
        )

    async def _fail(self, email_key: str, ip_key: str | None) -> NoReturn:
        await self._limiter.record_failure(email_key, self._policy.window_seconds)
        if ip_key:
            await self._limiter.record_failure(ip_key, self._policy.window_seconds)
        self._metrics.login_attempt("invalid")
        raise InvalidCredentials()

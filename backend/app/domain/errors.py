class DomainError(Exception):
    """Base de los errores de negocio. El adaptador HTTP los traduce a códigos de estado."""

    code = "domain_error"
    default_message = "Error de dominio"

    def __init__(self, message: str | None = None, details: list[str] | None = None) -> None:
        self.message = message or self.default_message
        self.details = details or []
        super().__init__(self.message)


class NotAuthenticated(DomainError):
    code = "not_authenticated"
    default_message = "Autenticación requerida"


class InvalidCredentials(NotAuthenticated):
    code = "invalid_credentials"
    default_message = "Credenciales inválidas"


class Forbidden(DomainError):
    code = "forbidden"
    default_message = "No tienes permiso para realizar esta acción"


class NotFound(DomainError):
    code = "not_found"
    default_message = "Recurso no encontrado"


class Conflict(DomainError):
    code = "conflict"
    default_message = "La operación entra en conflicto con el estado actual"


class EmailAlreadyRegistered(Conflict):
    code = "email_already_registered"
    default_message = "El correo ya está registrado"


class InvalidTransition(Conflict):
    code = "invalid_transition"
    default_message = "La operación no es válida para el estado actual del evento"


class ScheduleConflict(Conflict):
    code = "schedule_conflict"
    default_message = "El horario se solapa con otra sesión"


class EventFull(Conflict):
    code = "event_full"
    default_message = "El evento no tiene cupos disponibles"


class SessionFull(Conflict):
    code = "session_full"
    default_message = "La sesión no tiene cupos disponibles"


class AlreadyRegistered(Conflict):
    code = "already_registered"
    default_message = "Ya estás inscrito"


class ValidationFailed(DomainError):
    code = "validation_failed"
    default_message = "Datos inválidos"


class TooManyAttempts(DomainError):
    """Se superó el límite de intentos. `retry_after` son los segundos de espera."""

    code = "too_many_attempts"
    default_message = "Demasiados intentos. Intenta de nuevo más tarde"

    def __init__(self, retry_after: int) -> None:
        minutes = max(1, -(-retry_after // 60))  # redondea hacia arriba
        super().__init__(
            f"Demasiados intentos fallidos. Intenta de nuevo en {minutes} "
            f"{'minuto' if minutes == 1 else 'minutos'}."
        )
        self.retry_after = retry_after

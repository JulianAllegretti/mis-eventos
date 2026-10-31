from app.domain.errors import ValidationFailed

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
FULL_NAME_MAX_LENGTH = 120


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    local, separator, domain = normalized.partition("@")
    if not separator or not local or "." not in domain:
        raise ValidationFailed("Correo inválido")
    return normalized


def validate_password(password: str) -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValidationFailed(
            f"La contraseña debe tener entre {PASSWORD_MIN_LENGTH} "
            f"y {PASSWORD_MAX_LENGTH} caracteres"
        )


def validate_full_name(full_name: str) -> str:
    cleaned = full_name.strip()
    if not cleaned or len(cleaned) > FULL_NAME_MAX_LENGTH:
        raise ValidationFailed(f"El nombre debe tener entre 1 y {FULL_NAME_MAX_LENGTH} caracteres")
    return cleaned

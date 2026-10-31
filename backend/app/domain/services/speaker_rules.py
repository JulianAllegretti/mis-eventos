from app.domain.errors import ValidationFailed
from app.domain.services.credentials import normalize_email

NAME_MAX_LENGTH = 120
BIO_MAX_LENGTH = 2000


def validate_speaker_data(
    name: str, email: str | None, bio: str | None
) -> tuple[str, str | None, str | None]:
    problems: list[str] = []

    clean_name = name.strip()
    if not clean_name or len(clean_name) > NAME_MAX_LENGTH:
        problems.append(f"name: debe tener entre 1 y {NAME_MAX_LENGTH} caracteres")

    clean_email: str | None = None
    if email and email.strip():
        try:
            clean_email = normalize_email(email)
        except ValidationFailed:
            problems.append("email: correo inválido")

    clean_bio = bio.strip() if bio and bio.strip() else None
    if clean_bio and len(clean_bio) > BIO_MAX_LENGTH:
        problems.append(f"bio: máximo {BIO_MAX_LENGTH} caracteres")

    if problems:
        raise ValidationFailed("Datos de ponente inválidos", problems)
    return clean_name, clean_email, clean_bio

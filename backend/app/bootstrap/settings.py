from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o de .env en desarrollo)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"  # vacío = sin Redis (solo PostgreSQL)
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=60, ge=1)
    cookie_secure: bool = True
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    admin_email: str | None = None
    admin_password: str | None = None
    cache_ttl_seconds: int = Field(default=60, ge=1)
    # Intervalo de la tarea de cierre automático y reconciliación de cupos; 0 la desactiva.
    finish_job_interval_seconds: float = Field(default=60, ge=0)
    # Intentos de login fallidos permitidos por ventana (ver ADR 0003 / TDD §7).
    login_max_failures_per_email: int = Field(default=5, ge=1)
    login_max_failures_per_ip: int = Field(default=20, ge=1)
    login_window_seconds: int = Field(default=900, ge=1)
    # Hashes de contraseña simultáneos (cada uno usa 64 MiB): protege memoria y CPU en ráfagas.
    password_hash_concurrency: int = Field(default=4, ge=1)
    log_level: str = "INFO"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

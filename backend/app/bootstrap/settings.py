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
    log_level: str = "INFO"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

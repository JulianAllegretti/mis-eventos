"""Modelos de tabla (SQLModel). Solo se usan dentro de este adaptador; el dominio no los ve.

Las restricciones CHECK, índices y extensiones viven en las migraciones de Alembic.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, true
from sqlmodel import Field, SQLModel


def _timestamptz(nullable: bool = False) -> Column[datetime]:
    return Column(DateTime(timezone=True), nullable=nullable)


class UserTable(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(primary_key=True)
    email: str = Field(sa_column=Column(String(320), nullable=False, unique=True))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    full_name: str = Field(sa_column=Column(String(120), nullable=False))
    role: str = Field(sa_column=Column(String(20), nullable=False, server_default="attendee"))
    is_active: bool = Field(
        default=True, sa_column=Column(Boolean, nullable=False, server_default=true())
    )
    created_at: datetime = Field(sa_column=_timestamptz())


class SpeakerTable(SQLModel, table=True):
    __tablename__ = "speakers"

    id: UUID = Field(primary_key=True)
    name: str = Field(sa_column=Column(String(120), nullable=False))
    email: str | None = Field(default=None, sa_column=Column(String(320), nullable=True))
    bio: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by_id: UUID = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    )
    created_at: datetime = Field(sa_column=_timestamptz())


class EventTable(SQLModel, table=True):
    __tablename__ = "events"

    id: UUID = Field(primary_key=True)
    name: str = Field(sa_column=Column(String(200), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    location: str = Field(sa_column=Column(String(200), nullable=False))
    start_at: datetime = Field(sa_column=_timestamptz())
    end_at: datetime = Field(sa_column=_timestamptz())
    capacity: int = Field(sa_column=Column(Integer, nullable=False))
    registered_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    status: str = Field(sa_column=Column(String(20), nullable=False))
    organizer_id: UUID = Field(
        sa_column=Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    )
    closed_at: datetime | None = Field(default=None, sa_column=_timestamptz(nullable=True))
    closed_by_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
    )
    closed_source: str | None = Field(default=None, sa_column=Column(String(20), nullable=True))
    created_at: datetime = Field(sa_column=_timestamptz())
    updated_at: datetime = Field(sa_column=_timestamptz())

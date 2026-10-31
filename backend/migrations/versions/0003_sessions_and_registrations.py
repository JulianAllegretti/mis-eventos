"""Sesiones de agenda e inscripciones

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "speaker_id",
            sa.Uuid(),
            sa.ForeignKey("speakers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("registered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_at > start_at", name="ck_sessions_dates"),
        sa.CheckConstraint("capacity >= 1", name="ck_sessions_capacity"),
        sa.CheckConstraint(
            "registered_count >= 0 AND registered_count <= capacity", name="ck_sessions_registered"
        ),
    )
    op.create_index("ix_sessions_event_start", "sessions", ["event_id", "start_at"])
    # Un ponente no puede tener dos sesiones solapadas, ni siquiera bajo concurrencia.
    # Requiere la extensión btree_gist (creada en 0001). Rango [inicio, fin): adyacentes no chocan.
    op.execute(
        "ALTER TABLE sessions ADD CONSTRAINT ex_sessions_speaker_no_overlap "
        "EXCLUDE USING gist (speaker_id WITH =, tstzrange(start_at, end_at) WITH &&)"
    )

    op.create_table(
        "registrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "event_id", sa.Uuid(), sa.ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Una sola inscripción activa por usuario y evento (se puede volver a inscribir tras cancelar).
    op.create_index(
        "uq_registrations_active",
        "registrations",
        ["user_id", "event_id"],
        unique=True,
        postgresql_where=sa.text("cancelled_at IS NULL"),
    )
    op.create_index("ix_registrations_event", "registrations", ["event_id"])

    op.create_table(
        "session_registrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_session_registrations_active",
        "session_registrations",
        ["user_id", "session_id"],
        unique=True,
        postgresql_where=sa.text("cancelled_at IS NULL"),
    )
    op.create_index("ix_session_registrations_session", "session_registrations", ["session_id"])


def downgrade() -> None:
    op.drop_table("session_registrations")
    op.drop_table("registrations")
    op.drop_table("sessions")

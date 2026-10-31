"""Ponentes y eventos

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speakers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("email IS NULL OR email = lower(email)", name="ck_speakers_email_lower"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("registered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "organizer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("closed_source", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("capacity >= 1", name="ck_events_capacity"),
        sa.CheckConstraint("end_at > start_at", name="ck_events_dates"),
        sa.CheckConstraint(
            "registered_count >= 0 AND registered_count <= capacity", name="ck_events_registered"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'finished', 'cancelled')", name="ck_events_status"
        ),
        sa.CheckConstraint(
            "closed_source IS NULL OR closed_source IN ('manual', 'scheduler')",
            name="ck_events_closed_source",
        ),
        # Trazabilidad del cierre (ADR 0008): los campos closed_* se llenan juntos y solo
        # cuando el evento está finalizado o cancelado.
        sa.CheckConstraint(
            "(status IN ('finished', 'cancelled') "
            "AND closed_at IS NOT NULL AND closed_source IS NOT NULL) "
            "OR (status IN ('draft', 'published') "
            "AND closed_at IS NULL AND closed_source IS NULL AND closed_by_id IS NULL)",
            name="ck_events_closed_consistency",
        ),
        sa.CheckConstraint(
            "closed_source IS NULL OR ((closed_source = 'scheduler') = (closed_by_id IS NULL))",
            name="ck_events_closed_by",
        ),
    )
    op.create_index("ix_events_status_start", "events", ["status", "start_at"])
    op.create_index("ix_events_organizer", "events", ["organizer_id"])
    # Búsqueda por nombre con ILIKE '%texto%' (extensión pg_trgm creada en 0001).
    op.execute("CREATE INDEX ix_events_name_trgm ON events USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_events_name_trgm")
    op.drop_table("events")
    op.drop_table("speakers")

"""Add central domain event outbox and per-handler deliveries.

Revision ID: 20260825_0034
Revises: 20260822_0033
Create Date: 2026-08-25 20:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260825_0034"
down_revision = "20260822_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domain_event_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_name", sa.String(length=160), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("producer_module", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deliveries_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("event_version > 0", name="ck_domain_event_outbox_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_domain_event_outbox_event_id"),
    )
    op.create_index(
        "idx_domain_event_outbox_pending",
        "domain_event_outbox",
        ["processed_at", "available_at", "created_at"],
        unique=False,
    )
    op.create_table(
        "event_delivery",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handler_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=160), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','SUCCEEDED','DEAD_LETTER')",
            name="ck_event_delivery_status",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_id"], ["domain_event_outbox.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "handler_id", name="uq_event_delivery_event_handler"
        ),
    )
    op.create_index(
        "idx_event_delivery_due",
        "event_delivery",
        ["status", "available_at", "locked_at"],
        unique=False,
    )
    op.create_index(
        "idx_event_delivery_outbox",
        "event_delivery",
        ["outbox_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_event_delivery_outbox", table_name="event_delivery")
    op.drop_index("idx_event_delivery_due", table_name="event_delivery")
    op.drop_table("event_delivery")
    op.drop_index("idx_domain_event_outbox_pending", table_name="domain_event_outbox")
    op.drop_table("domain_event_outbox")

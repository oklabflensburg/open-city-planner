"""add Mastodon social publication outbox

Revision ID: 20260816_0017
Revises: 20260816_0016
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260816_0017"
down_revision = "20260816_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_audit_logs", sa.Column("resource_type", sa.String(40)))
    op.add_column("admin_audit_logs", sa.Column("resource_id", postgresql.UUID(as_uuid=True)))
    op.add_column("admin_audit_logs", sa.Column("metadata", postgresql.JSONB()))
    op.create_table(
        "social_publication_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(24), server_default="MASTODON", nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("mastodon_status_id", sa.String(120)),
        sa.Column("mastodon_status_url", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("dry_run", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','PROCESSING','PUBLISHED','FAILED','CANCELLED','DRY_RUN')", name="ck_social_outbox_status"),
    )
    op.create_index("idx_social_outbox_due", "social_publication_outbox", ["status", "next_attempt_at"])
    op.create_index("idx_social_outbox_resource", "social_publication_outbox", ["resource_type", "resource_id"])
    op.create_index(
        "uq_social_outbox_pending_resource", "social_publication_outbox",
        ["platform", "resource_type", "resource_id"], unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_table(
        "social_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("outbox_event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("platform", sa.String(24), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("remote_id", sa.String(120)),
        sa.Column("remote_url", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("dry_run", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("content_hash", "resource_id", "event_type", name="uq_social_publication_content"),
    )
    op.create_index("idx_social_publications_published", "social_publications", ["published_at"])


def downgrade() -> None:
    op.drop_table("social_publications")
    op.drop_table("social_publication_outbox")
    op.drop_column("admin_audit_logs", "metadata")
    op.drop_column("admin_audit_logs", "resource_id")
    op.drop_column("admin_audit_logs", "resource_type")

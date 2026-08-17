"""add persistent user notifications

Revision ID: 20260817_0022
Revises: 20260817_0021
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260817_0022"
down_revision = "20260817_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipient_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("actor_type", sa.String(16), nullable=False, server_default="SYSTEM"),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(24), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.String(600), nullable=False),
        sa.Column("resource_type", sa.String(32)),
        sa.Column("resource_id", sa.String(160)),
        sa.Column("resource_slug", sa.String(255)),
        sa.Column("action_url", sa.String(500)),
        sa.Column("action_label", sa.String(80)),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("dedupe_key", sa.String(255)),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.CheckConstraint(
            "category IN ('GIS','DATA','OSM','SOCIAL','ACCOUNT','ADMIN','SYSTEM')",
            name="ck_notifications_category",
        ),
        sa.CheckConstraint(
            "priority IN ('INFO','SUCCESS','WARNING','ERROR','ACTION_REQUIRED')",
            name="ck_notifications_priority",
        ),
        sa.CheckConstraint("actor_type IN ('USER','SYSTEM')", name="ck_notifications_actor_type"),
    )
    op.create_index(
        "idx_notifications_recipient_created",
        "notifications",
        ["recipient_user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_notifications_recipient_unread_created",
        "notifications",
        ["recipient_user_id", "is_read", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_notifications_dedupe",
        "notifications",
        ["recipient_user_id", "dedupe_key", sa.text("created_at DESC")],
    )

    op.create_table(
        "notification_preferences",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_gis", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_osm", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_area_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_social", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_account", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_system", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "notification_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(160), nullable=False),
        sa.Column(
            "event_types", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "user_id", "resource_type", "resource_id", name="uq_notification_subscription_resource"
        ),
    )
    op.create_index(
        "idx_notification_subscriptions_resource",
        "notification_subscriptions",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_table("notification_subscriptions")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")

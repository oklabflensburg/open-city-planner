"""E-Mail-Kampagnen und Mehrkanal-Benachrichtigungen

Revision ID: 20260819_0031
Revises: 20260819_0030
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260819_0031"
down_revision = "20260819_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internal_name", sa.String(180), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("intro", sa.Text()),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("action_url", sa.Text()),
        sa.Column("action_label", sa.String(80)),
        sa.Column("campaign_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), server_default="DRAFT", nullable=False),
        sa.Column("recipient_scope", sa.String(32), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("recipient_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "campaign_type IN ('LEGAL','SERVICE','NEWSLETTER','SYSTEM')",
            name="ck_email_campaign_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SCHEDULED','PROCESSING','COMPLETED','CANCELLED')",
            name="ck_email_campaign_status",
        ),
        sa.CheckConstraint(
            "recipient_scope IN ('ALL_ACTIVE_USERS','VERIFIED_USERS','SUPERUSERS')",
            name="ck_email_campaign_recipient_scope",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_email_campaigns_status_scheduled", "email_campaigns", ["status", "scheduled_at"]
    )
    op.create_table(
        "email_campaign_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("recipient_name", sa.String(180), nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','SENT','FAILED','SKIPPED','CANCELLED')",
            name="ck_email_campaign_delivery_status",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["email_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_email_campaign_delivery_user"),
    )
    op.create_index(
        "idx_email_campaign_deliveries_status",
        "email_campaign_deliveries",
        ["campaign_id", "status"],
    )
    op.create_table(
        "email_unsubscribe_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_email_unsubscribe_token_hash", "email_unsubscribe_tokens", ["token_hash"])

    op.add_column(
        "notifications",
        sa.Column("in_app_visible", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    for column in (
        "email_enabled",
        "email_notify_gis",
        "email_notify_osm",
        "email_notify_area_updates",
        "email_notify_social",
        "email_notify_system",
        "newsletter_enabled",
    ):
        op.add_column(
            "notification_preferences",
            sa.Column(column, sa.Boolean(), server_default=sa.false(), nullable=False),
        )

    op.add_column(
        "email_outbox",
        sa.Column("delivery_type", sa.String(24), server_default="WELCOME", nullable=False),
    )
    op.add_column("email_outbox", sa.Column("idempotency_key", sa.String(255)))
    op.add_column("email_outbox", sa.Column("campaign_id", postgresql.UUID(as_uuid=True)))
    op.add_column("email_outbox", sa.Column("campaign_delivery_id", postgresql.UUID(as_uuid=True)))
    op.add_column("email_outbox", sa.Column("notification_id", postgresql.UUID(as_uuid=True)))
    op.drop_constraint("email_outbox_user_id_fkey", "email_outbox", type_="foreignkey")
    op.alter_column("email_outbox", "user_id", nullable=True)
    op.create_foreign_key(
        "fk_email_outbox_user",
        "email_outbox",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE email_outbox SET idempotency_key = 'welcome:' || user_id::text")
    op.alter_column("email_outbox", "idempotency_key", nullable=False)
    op.drop_constraint("uq_email_outbox_template_user", "email_outbox", type_="unique")
    op.create_unique_constraint(
        "uq_email_outbox_idempotency_key", "email_outbox", ["idempotency_key"]
    )
    op.create_check_constraint(
        "ck_email_outbox_delivery_type",
        "email_outbox",
        "delivery_type IN ('WELCOME','CAMPAIGN','NOTIFICATION')",
    )
    op.drop_constraint("ck_email_outbox_status", "email_outbox", type_="check")
    op.create_check_constraint(
        "ck_email_outbox_status",
        "email_outbox",
        "status IN ('PENDING','PROCESSING','SENT','FAILED','CANCELLED')",
    )
    op.create_foreign_key(
        "fk_email_outbox_campaign",
        "email_outbox",
        "email_campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_email_outbox_campaign_delivery",
        "email_outbox",
        "email_campaign_deliveries",
        ["campaign_delivery_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_email_outbox_notification",
        "email_outbox",
        "notifications",
        ["notification_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_email_outbox_notification", "email_outbox", type_="foreignkey")
    op.drop_constraint("fk_email_outbox_campaign_delivery", "email_outbox", type_="foreignkey")
    op.drop_constraint("fk_email_outbox_campaign", "email_outbox", type_="foreignkey")
    op.drop_constraint("fk_email_outbox_user", "email_outbox", type_="foreignkey")
    op.drop_constraint("ck_email_outbox_delivery_type", "email_outbox", type_="check")
    op.drop_constraint("ck_email_outbox_status", "email_outbox", type_="check")
    # Nur die bereits vor dieser Migration unterstützten Welcome-Einträge können
    # im alten Schema ohne Informationsverlust dargestellt werden.
    op.execute("DELETE FROM email_outbox WHERE delivery_type <> 'WELCOME'")
    op.execute("DELETE FROM email_outbox WHERE user_id IS NULL")
    op.execute("UPDATE email_outbox SET status = 'FAILED' WHERE status = 'CANCELLED'")
    op.create_check_constraint(
        "ck_email_outbox_status",
        "email_outbox",
        "status IN ('PENDING','PROCESSING','SENT','FAILED')",
    )
    op.drop_constraint("uq_email_outbox_idempotency_key", "email_outbox", type_="unique")
    op.create_unique_constraint(
        "uq_email_outbox_template_user", "email_outbox", ["template_key", "user_id"]
    )
    for column in (
        "notification_id",
        "campaign_delivery_id",
        "campaign_id",
        "idempotency_key",
        "delivery_type",
    ):
        op.drop_column("email_outbox", column)
    op.alter_column("email_outbox", "user_id", nullable=False)
    op.create_foreign_key(
        "email_outbox_user_id_fkey",
        "email_outbox",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for column in (
        "newsletter_enabled",
        "email_notify_system",
        "email_notify_social",
        "email_notify_area_updates",
        "email_notify_osm",
        "email_notify_gis",
        "email_enabled",
    ):
        op.drop_column("notification_preferences", column)
    op.drop_column("notifications", "in_app_visible")
    op.drop_index("idx_email_unsubscribe_token_hash", table_name="email_unsubscribe_tokens")
    op.drop_table("email_unsubscribe_tokens")
    op.drop_index("idx_email_campaign_deliveries_status", table_name="email_campaign_deliveries")
    op.drop_table("email_campaign_deliveries")
    op.drop_index("idx_email_campaigns_status_scheduled", table_name="email_campaigns")
    op.drop_table("email_campaigns")

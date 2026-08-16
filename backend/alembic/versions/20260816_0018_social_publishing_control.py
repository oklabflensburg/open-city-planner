"""add persistent social publishing controls and screenshots

Revision ID: 20260816_0018
Revises: 20260816_0017
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260816_0018"
down_revision = "20260816_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_social_outbox_pending_resource", table_name="social_publication_outbox")
    op.drop_constraint("ck_social_outbox_status", "social_publication_outbox", type_="check")
    op.create_check_constraint(
        "ck_social_outbox_status",
        "social_publication_outbox",
        "status IN ('PENDING_APPROVAL','PENDING','PROCESSING','PUBLISHED','FAILED','CANCELLED','DRY_RUN')",
    )
    op.create_index(
        "uq_social_outbox_pending_resource",
        "social_publication_outbox",
        ["platform", "resource_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING','PENDING_APPROVAL')"),
    )
    op.add_column("social_publication_outbox", sa.Column("mastodon_media_id", sa.String(120)))
    op.add_column("social_publication_outbox", sa.Column("screenshot_path", sa.Text()))
    op.add_column("social_publication_outbox", sa.Column("screenshot_target_url", sa.Text()))
    op.add_column("social_publication_outbox", sa.Column("screenshot_alt_text", sa.Text()))
    op.add_column("social_publication_outbox", sa.Column("screenshot_created_at", sa.DateTime(timezone=True)))
    op.add_column("social_publications", sa.Column("remote_media_id", sa.String(120)))
    op.create_table(
        "social_publishing_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(24), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approval_mode", sa.String(16), nullable=False, server_default="AUTOMATIC"),
        sa.Column("default_visibility", sa.String(16), nullable=False, server_default="public"),
        sa.Column("language", sa.String(8), nullable=False, server_default="de"),
        sa.Column("debounce_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("default_hashtags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[\"Flensburg\",\"OpenData\",\"Stadtplaner\"]'::jsonb")),
        sa.Column("enabled_events", postgresql.JSONB(), nullable=False, server_default=sa.text("'[\"AREA_CREATED\",\"AREA_PUBLIC_DATA_UPDATED\",\"AREA_BOUNDARY_UPDATED\",\"AREA_STATISTICS_UPDATED\",\"AREA_STATISTICS_BULK_UPDATED\"]'::jsonb")),
        sa.Column("screenshot_viewport", sa.String(16), nullable=False, server_default="LANDSCAPE_16_9"),
        sa.Column("screenshot_show_map", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("screenshot_show_facts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("screenshot_show_pois", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("screenshot_show_branding", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("approval_mode IN ('AUTOMATIC','MANUAL','DRY_RUN')", name="ck_social_settings_approval"),
        sa.CheckConstraint("default_visibility IN ('public','unlisted','private')", name="ck_social_settings_visibility"),
        sa.CheckConstraint("debounce_seconds BETWEEN 0 AND 86400", name="ck_social_settings_debounce"),
        sa.CheckConstraint("screenshot_viewport IN ('LANDSCAPE_16_9','LANDSCAPE_OG','SQUARE')", name="ck_social_settings_viewport"),
    )
    op.execute(sa.text("""
        INSERT INTO social_publishing_settings
          (id, platform, enabled, approval_mode, default_visibility, language,
           debounce_seconds, default_hashtags, enabled_events, screenshot_viewport,
           screenshot_show_map, screenshot_show_facts, screenshot_show_pois,
           screenshot_show_branding)
        VALUES
          ('00000000-0000-4000-8000-000000000001', 'MASTODON', true, 'AUTOMATIC',
           'public', 'de', 300, '["Flensburg","OpenData","Stadtplaner"]'::jsonb,
           '["AREA_CREATED","AREA_PUBLIC_DATA_UPDATED","AREA_BOUNDARY_UPDATED","AREA_STATISTICS_UPDATED","AREA_STATISTICS_BULK_UPDATED"]'::jsonb,
           'LANDSCAPE_16_9', true, true, false, true)
    """))


def downgrade() -> None:
    op.drop_table("social_publishing_settings")
    op.drop_column("social_publications", "remote_media_id")
    for column in ("screenshot_created_at", "screenshot_alt_text", "screenshot_target_url", "screenshot_path", "mastodon_media_id"):
        op.drop_column("social_publication_outbox", column)
    op.drop_index("uq_social_outbox_pending_resource", table_name="social_publication_outbox")
    op.drop_constraint("ck_social_outbox_status", "social_publication_outbox", type_="check")
    op.create_check_constraint("ck_social_outbox_status", "social_publication_outbox", "status IN ('PENDING','PROCESSING','PUBLISHED','FAILED','CANCELLED','DRY_RUN')")
    op.create_index("uq_social_outbox_pending_resource", "social_publication_outbox", ["platform", "resource_type", "resource_id"], unique=True, postgresql_where=sa.text("status = 'PENDING'"))

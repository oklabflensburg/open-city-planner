"""add OSM polygon adoption social publishing controls

Revision ID: 20260817_0021
Revises: 20260817_0020
"""

import sqlalchemy as sa

from alembic import op

revision = "20260817_0021"
down_revision = "20260817_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "social_publishing_settings",
        sa.Column(
            "polygon_osm_adoption_link_target",
            sa.String(16), nullable=False, server_default="DETAIL_PAGE",
        ),
    )
    op.create_check_constraint(
        "ck_social_settings_polygon_link_target",
        "social_publishing_settings",
        "polygon_osm_adoption_link_target IN ('DETAIL_PAGE','GIS')",
    )
    op.create_index(
        "uq_social_outbox_polygon_adopted",
        "social_publication_outbox",
        ["event_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text("event_type = 'POLYGON_ADOPTED_FROM_OSM'"),
    )


def downgrade() -> None:
    op.drop_index("uq_social_outbox_polygon_adopted", table_name="social_publication_outbox")
    op.drop_constraint(
        "ck_social_settings_polygon_link_target",
        "social_publishing_settings",
        type_="check",
    )
    op.drop_column("social_publishing_settings", "polygon_osm_adoption_link_target")

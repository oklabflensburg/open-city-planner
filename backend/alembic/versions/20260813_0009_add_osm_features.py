"""add canonical local OSM feature import table

Revision ID: 20260813_0009
Revises: 20260813_0008
"""

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260813_0009"
down_revision = "20260813_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "osm_features",
        sa.Column("osm_type", sa.String(length=8), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="GEOMETRY", srid=4326, spatial_index=False
            ),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "osm_type IN ('node', 'way', 'relation')", name="ck_osm_features_type"
        ),
        sa.PrimaryKeyConstraint("osm_type", "osm_id"),
    )
    op.create_index(
        "idx_osm_features_geometry",
        "osm_features",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_osm_features_tags",
        "osm_features",
        ["tags"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_osm_features_tags", table_name="osm_features")
    op.drop_index("idx_osm_features_geometry", table_name="osm_features")
    op.drop_table("osm_features")

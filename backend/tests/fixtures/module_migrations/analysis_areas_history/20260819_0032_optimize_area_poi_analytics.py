"""Gebiets-POI-Analytics räumlich vorfiltern

Revision ID: 20260819_0032
Revises: 20260819_0031
"""

import sqlalchemy as sa

from alembic import op

revision = "20260819_0032"
down_revision = "20260819_0031"
branch_labels = None
depends_on = None

POI_PREDICATE = sa.text("tags ? 'shop' OR tags ? 'amenity' OR tags ? 'tourism' OR tags ? 'leisure'")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "idx_osm_features_poi_geometry",
            "osm_features",
            ["geometry"],
            unique=False,
            postgresql_using="gist",
            postgresql_where=POI_PREDICATE,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "idx_osm_features_poi_geometry",
            table_name="osm_features",
            postgresql_concurrently=True,
        )

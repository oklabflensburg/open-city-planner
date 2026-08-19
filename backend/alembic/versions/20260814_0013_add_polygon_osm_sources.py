"""add polygon OSM sources and occupancy provenance

Revision ID: 20260814_0013
Revises: 20260814_0012
"""

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260814_0013"
down_revision = "20260814_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_polygons", "geometry",
        type_=Geometry("GEOMETRY", srid=4326),
        postgresql_using="geometry::geometry(Geometry,4326)",
    )
    op.add_column("user_polygons", sa.Column("occupancy_source", sa.String(16), server_default="UNKNOWN", nullable=False))
    op.add_column("user_polygons", sa.Column("occupancy_source_tag", sa.String(120), nullable=True))
    op.add_column("user_polygons", sa.Column("occupancy_source_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_user_polygons_occupancy_source", "user_polygons",
        "occupancy_source IN ('OSM', 'MANUAL', 'IMPORTED', 'CALCULATED', 'UNKNOWN')",
    )
    op.create_table(
        "polygon_osm_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("polygon_id", sa.Integer(), sa.ForeignKey("user_polygons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("osm_type", sa.String(8), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("osm_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_geometry", Geometry("GEOMETRY", srid=4326), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("polygon_id", "osm_type", "osm_id", name="uq_polygon_osm_source"),
    )
    op.create_index("idx_polygon_osm_sources_osm", "polygon_osm_sources", ["osm_type", "osm_id"])
    op.create_index("idx_polygon_osm_sources_polygon", "polygon_osm_sources", ["polygon_id"])


def downgrade() -> None:
    op.drop_index("idx_polygon_osm_sources_polygon", table_name="polygon_osm_sources")
    op.drop_index("idx_polygon_osm_sources_osm", table_name="polygon_osm_sources")
    op.drop_table("polygon_osm_sources")
    op.drop_constraint("ck_user_polygons_occupancy_source", "user_polygons", type_="check")
    op.drop_column("user_polygons", "occupancy_source_updated_at")
    op.drop_column("user_polygons", "occupancy_source_tag")
    op.drop_column("user_polygons", "occupancy_source")
    op.alter_column(
        "user_polygons", "geometry",
        type_=Geometry("POLYGON", srid=4326),
        postgresql_using="geometry::geometry(Polygon,4326)",
    )

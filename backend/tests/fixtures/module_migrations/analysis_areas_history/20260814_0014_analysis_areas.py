"""add hierarchical spatial analysis areas

Revision ID: 20260814_0014
Revises: 20260814_0013
"""

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260814_0014"
down_revision = "20260814_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("area_type", sa.String(16), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("analysis_areas.id", ondelete="SET NULL")),
        sa.Column("geometry", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.Column("centroid", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("area_m2", sa.Float(), nullable=False),
        sa.Column("source", sa.String(24), server_default="OSM", nullable=False),
        sa.Column("source_osm_type", sa.String(8)),
        sa.Column("source_osm_id", sa.BigInteger()),
        sa.Column("source_admin_level", sa.Integer()),
        sa.Column("source_place", sa.String(40)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("area_type IN ('MUNICIPALITY','DISTRICT','QUARTER')", name="ck_analysis_areas_type"),
        sa.CheckConstraint("source IN ('OSM','MANUAL')", name="ck_analysis_areas_source"),
        sa.UniqueConstraint("source", "source_osm_type", "source_osm_id", name="uq_analysis_areas_source_osm"),
    )
    op.create_index("idx_analysis_areas_parent", "analysis_areas", ["parent_id"])
    op.create_index("idx_analysis_areas_type", "analysis_areas", ["area_type"])
    op.create_index("idx_analysis_areas_geometry", "analysis_areas", ["geometry"], postgresql_using="gist")
    op.create_table(
        "polygon_analysis_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("polygon_id", sa.Integer(), sa.ForeignKey("user_polygons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_area_id", sa.Integer(), sa.ForeignKey("analysis_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_type", sa.String(16), server_default="POINT_ON_SURFACE", nullable=False),
        sa.Column("overlap_ratio", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("polygon_id", "analysis_area_id", name="uq_polygon_analysis_area"),
    )
    op.create_index("idx_polygon_analysis_areas_polygon", "polygon_analysis_areas", ["polygon_id"])
    op.create_index("idx_polygon_analysis_areas_area", "polygon_analysis_areas", ["analysis_area_id"])


def downgrade() -> None:
    op.drop_table("polygon_analysis_areas")
    op.drop_table("analysis_areas")

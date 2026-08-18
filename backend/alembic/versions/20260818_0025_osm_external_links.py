"""harden OSM external link state and backfill adopted polygon snapshots

Revision ID: 20260818_0025
Revises: 20260818_0024
"""

import sqlalchemy as sa

from alembic import op

revision = "20260818_0025"
down_revision = "20260818_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "analysis_areas", "source_osm_wikidata",
        existing_type=sa.String(length=32), type_=sa.String(length=255),
    )
    op.drop_constraint("ck_analysis_areas_wikidata_status", "analysis_areas", type_="check")
    op.create_check_constraint(
        "ck_analysis_areas_wikidata_status",
        "analysis_areas",
        "wikidata_match_status IS NULL OR wikidata_match_status IN "
        "('VERIFIED','AUTO_MATCHED','AMBIGUOUS','NOT_FOUND','INVALID','CONFLICT')",
    )
    op.create_index("idx_analysis_areas_wikidata_id", "analysis_areas", ["wikidata_id"])
    op.execute("""
      UPDATE polygon_osm_sources source SET
        osm_snapshot=feature.tags,
        source_geometry=feature.geometry,
        source_updated_at=feature.imported_at
      FROM osm_features feature
      WHERE source.osm_type=feature.osm_type AND source.osm_id=feature.osm_id
    """)


def downgrade() -> None:
    op.drop_index("idx_analysis_areas_wikidata_id", table_name="analysis_areas")
    op.drop_constraint("ck_analysis_areas_wikidata_status", "analysis_areas", type_="check")
    op.create_check_constraint(
        "ck_analysis_areas_wikidata_status",
        "analysis_areas",
        "wikidata_match_status IS NULL OR wikidata_match_status IN "
        "('VERIFIED','AUTO_MATCHED','AMBIGUOUS','NOT_FOUND','CONFLICT')",
    )
    op.alter_column(
        "analysis_areas", "source_osm_wikidata",
        existing_type=sa.String(length=255), type_=sa.String(length=32),
    )

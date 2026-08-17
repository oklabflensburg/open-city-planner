"""add persistent Wikidata enrichment to analysis areas

Revision ID: 20260817_0023
Revises: 20260817_0022
"""

import sqlalchemy as sa

from alembic import op

revision = "20260817_0023"
down_revision = "20260817_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("source_osm_wikidata", sa.String(32)),
        sa.Column("source_osm_wikipedia", sa.String(255)),
        sa.Column("wikidata_id", sa.String(32)),
        sa.Column("wikipedia_title", sa.String(255)),
        sa.Column("wikidata_label", sa.String(200)),
        sa.Column("wikidata_description", sa.String(500)),
        sa.Column("wikidata_match_source", sa.String(24)),
        sa.Column("wikidata_match_status", sa.String(24)),
        sa.Column("wikidata_match_confidence", sa.Float()),
        sa.Column("wikidata_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("wikidata_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    ):
        op.add_column("analysis_areas", column)
    op.create_check_constraint(
        "ck_analysis_areas_wikidata_id", "analysis_areas",
        "wikidata_id IS NULL OR wikidata_id ~ '^Q[1-9][0-9]*$'",
    )
    op.create_check_constraint(
        "ck_analysis_areas_wikidata_source", "analysis_areas",
        "wikidata_match_source IS NULL OR wikidata_match_source IN "
        "('OSM_WIKIDATA','OSM_WIKIPEDIA','WIKIDATA_SEARCH','MANUAL')",
    )
    op.create_check_constraint(
        "ck_analysis_areas_wikidata_status", "analysis_areas",
        "wikidata_match_status IS NULL OR wikidata_match_status IN "
        "('VERIFIED','AUTO_MATCHED','AMBIGUOUS','NOT_FOUND','CONFLICT')",
    )
    op.execute("""
      UPDATE analysis_areas area SET
        source_osm_wikidata=feature.tags->>'wikidata',
        source_osm_wikipedia=feature.tags->>'wikipedia'
      FROM osm_features feature
      WHERE area.source='OSM'
        AND area.source_osm_type=feature.osm_type
        AND area.source_osm_id=feature.osm_id
    """)


def downgrade() -> None:
    op.drop_constraint("ck_analysis_areas_wikidata_status", "analysis_areas", type_="check")
    op.drop_constraint("ck_analysis_areas_wikidata_source", "analysis_areas", type_="check")
    op.drop_constraint("ck_analysis_areas_wikidata_id", "analysis_areas", type_="check")
    for name in (
        "wikidata_verified", "wikidata_last_checked_at", "wikidata_match_confidence",
        "wikidata_match_status", "wikidata_match_source", "wikidata_description",
        "wikidata_label", "wikipedia_title", "wikidata_id", "source_osm_wikipedia",
        "source_osm_wikidata",
    ):
        op.drop_column("analysis_areas", name)

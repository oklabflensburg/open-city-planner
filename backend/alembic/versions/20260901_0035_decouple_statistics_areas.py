"""Decouple municipal statistics from Analysis Areas persistence.

Revision ID: 20260901_0035
Revises: 20260825_0034
"""

import sqlalchemy as sa

from alembic import op

revision = "20260901_0035"
down_revision = "20260825_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_area_mappings",
        sa.Column("level", sa.String(length=40), nullable=True),
    )
    op.execute(
        """
        UPDATE external_area_mappings mapping
        SET level = area.area_type
        FROM analysis_areas area
        WHERE area.id = mapping.analysis_area_id
        """
    )
    op.alter_column("external_area_mappings", "level", nullable=False)

    op.add_column(
        "statistical_observations",
        sa.Column("statistical_area_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE statistical_observations observation
        SET statistical_area_id = mapping.id
        FROM external_area_mappings mapping
        WHERE mapping.analysis_area_id = observation.analysis_area_id
        """
    )
    op.alter_column("statistical_observations", "statistical_area_id", nullable=False)
    op.drop_constraint(
        "uq_statistical_observation", "statistical_observations", type_="unique"
    )
    op.drop_index(
        "idx_statistical_observations_area_period",
        table_name="statistical_observations",
    )
    op.drop_constraint(
        "statistical_observations_analysis_area_id_fkey",
        "statistical_observations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "statistical_observations_statistical_area_id_fkey",
        "statistical_observations",
        "external_area_mappings",
        ["statistical_area_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_statistical_observation",
        "statistical_observations",
        ["metric_id", "statistical_area_id", "period_start", "source_area_id"],
    )
    op.create_index(
        "idx_statistical_observations_area_period",
        "statistical_observations",
        ["statistical_area_id", "period_start"],
    )
    op.drop_column("statistical_observations", "analysis_area_id")

    op.drop_index("idx_external_area_mapping_area", table_name="external_area_mappings")
    op.drop_constraint(
        "external_area_mappings_analysis_area_id_fkey",
        "external_area_mappings",
        type_="foreignkey",
    )
    op.drop_column("external_area_mappings", "analysis_area_id")
    op.create_index(
        "idx_external_area_mapping_name_level",
        "external_area_mappings",
        ["external_area_name", "level"],
    )


def downgrade() -> None:
    op.add_column(
        "external_area_mappings",
        sa.Column("analysis_area_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE external_area_mappings mapping
        SET analysis_area_id = area.id
        FROM analysis_areas area
        WHERE area.name = mapping.external_area_name
          AND area.area_type = mapping.level
        """
    )
    op.alter_column("external_area_mappings", "analysis_area_id", nullable=False)
    op.create_foreign_key(
        "external_area_mappings_analysis_area_id_fkey",
        "external_area_mappings",
        "analysis_areas",
        ["analysis_area_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(
        "idx_external_area_mapping_name_level", table_name="external_area_mappings"
    )
    op.create_index(
        "idx_external_area_mapping_area",
        "external_area_mappings",
        ["analysis_area_id"],
    )

    op.add_column(
        "statistical_observations",
        sa.Column("analysis_area_id", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE statistical_observations observation
        SET analysis_area_id = mapping.analysis_area_id
        FROM external_area_mappings mapping
        WHERE mapping.id = observation.statistical_area_id
        """
    )
    op.alter_column("statistical_observations", "analysis_area_id", nullable=False)
    op.drop_constraint(
        "uq_statistical_observation", "statistical_observations", type_="unique"
    )
    op.drop_index(
        "idx_statistical_observations_area_period",
        table_name="statistical_observations",
    )
    op.drop_constraint(
        "statistical_observations_statistical_area_id_fkey",
        "statistical_observations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "statistical_observations_analysis_area_id_fkey",
        "statistical_observations",
        "analysis_areas",
        ["analysis_area_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_statistical_observation",
        "statistical_observations",
        ["metric_id", "analysis_area_id", "period_start", "source_area_id"],
    )
    op.create_index(
        "idx_statistical_observations_area_period",
        "statistical_observations",
        ["analysis_area_id", "period_start"],
    )
    op.drop_column("statistical_observations", "statistical_area_id")
    op.drop_column("external_area_mappings", "level")

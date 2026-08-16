"""add normalized municipal statistics storage

Revision ID: 20260816_0016
Revises: 20260814_0015
"""

import sqlalchemy as sa

from alembic import op

revision = "20260816_0016"
down_revision = "20260814_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "statistical_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("external_dataset_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license", sa.String(160), nullable=False),
        sa.Column("update_frequency", sa.String(40), nullable=False),
        sa.Column("last_import_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "external_dataset_id", name="uq_statistical_dataset_source"),
    )
    op.create_table(
        "statistical_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("statistical_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(120), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("value_type", sa.String(24), server_default="numeric", nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("aggregation_method", sa.String(40)),
        sa.Column("public", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_statistical_metrics_dataset", "statistical_metrics", ["dataset_id"])
    op.create_table(
        "external_area_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("external_area_id", sa.String(80), nullable=False),
        sa.Column("external_area_name", sa.String(200), nullable=False),
        sa.Column("analysis_area_id", sa.Integer(), sa.ForeignKey("analysis_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "external_area_id", name="uq_external_area_mapping_id"),
        sa.UniqueConstraint("source", "external_area_name", name="uq_external_area_mapping_name"),
    )
    op.create_index("idx_external_area_mapping_area", "external_area_mappings", ["analysis_area_id"])
    op.create_table(
        "statistical_observations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("metric_id", sa.Integer(), sa.ForeignKey("statistical_metrics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_area_id", sa.Integer(), sa.ForeignKey("analysis_areas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_type", sa.String(24), server_default="YEAR", nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value_numeric", sa.Numeric(20, 4)),
        sa.Column("value_text", sa.Text()),
        sa.Column("source_area_id", sa.String(80), nullable=False),
        sa.Column("source_row_hash", sa.String(64), nullable=False),
        sa.Column("is_calculated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("metric_id", "analysis_area_id", "period_start", "source_area_id", name="uq_statistical_observation"),
    )
    op.create_index("idx_statistical_observations_area_period", "statistical_observations", ["analysis_area_id", "period_start"])
    op.create_index("idx_statistical_observations_metric_period", "statistical_observations", ["metric_id", "period_start"])
    op.create_table(
        "statistical_import_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("rows_downloaded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_imported", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_rejected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64)),
        sa.Column("schema_hash", sa.String(64)),
        sa.Column("column_names", sa.Text()),
    )
    op.create_index("idx_statistical_import_runs_source_started", "statistical_import_runs", ["source", "started_at"])
    op.execute("INSERT INTO cache_versions(namespace,version,updated_at) VALUES ('statistics',1,now()) ON CONFLICT (namespace) DO NOTHING")


def downgrade() -> None:
    op.drop_table("statistical_import_runs")
    op.drop_table("statistical_observations")
    op.drop_table("external_area_mappings")
    op.drop_table("statistical_metrics")
    op.drop_table("statistical_datasets")
    op.execute("DELETE FROM cache_versions WHERE namespace='statistics'")

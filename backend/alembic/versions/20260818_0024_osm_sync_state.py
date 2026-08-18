"""add durable OSM synchronization state

Revision ID: 20260818_0024
Revises: 20260817_0023
"""

import sqlalchemy as sa

from alembic import op

revision = "20260818_0024"
down_revision = "20260817_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "osm_sync_state",
        sa.Column("singleton", sa.Boolean(), primary_key=True, server_default=sa.true()),
        sa.Column("sequence", sa.BigInteger()),
        sa.Column("osm_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("singleton", name="ck_osm_sync_state_singleton"),
    )


def downgrade() -> None:
    op.drop_table("osm_sync_state")

"""add durable cache namespace versions

Revision ID: 20260814_0015
Revises: 20260814_0014
"""

import sqlalchemy as sa
from alembic import op

revision = "20260814_0015"
down_revision = "20260814_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache_versions",
        sa.Column("namespace", sa.String(32), primary_key=True),
        sa.Column("version", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    versions = sa.table(
        "cache_versions",
        sa.column("namespace", sa.String),
        sa.column("version", sa.BigInteger),
    )
    op.bulk_insert(
        versions,
        [
            {"namespace": name, "version": 1}
            for name in ("osm", "analytics", "analysis-areas", "polygons")
        ],
    )


def downgrade() -> None:
    op.drop_table("cache_versions")

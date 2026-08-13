"""add centrally maintained city metrics

Revision ID: 20260813_0008
Revises: 20260813_0007
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260813_0008"
down_revision = "20260813_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "city_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("vacancy_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("chain_store_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("centrality_index", sa.Numeric(8, 2), nullable=True),
        sa.Column("purchasing_power_index", sa.Numeric(8, 2), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("city_metrics")

"""add polygon analytics indexes

Revision ID: 20260813_0007
Revises: 20260812_0006
"""

from alembic import op

revision = "20260813_0007"
down_revision = "20260812_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_user_polygons_category", "user_polygons", ["category"])
    op.create_index("idx_user_polygons_floor", "user_polygons", ["floor"])


def downgrade() -> None:
    op.drop_index("idx_user_polygons_floor", table_name="user_polygons")
    op.drop_index("idx_user_polygons_category", table_name="user_polygons")

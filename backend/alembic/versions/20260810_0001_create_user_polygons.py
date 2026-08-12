"""create user polygons

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "user_polygons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("geometry", geoalchemy2.types.Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("idx_user_polygons_uuid", "user_polygons", ["uuid"])
    op.create_index("idx_user_polygons_created_at", "user_polygons", ["created_at"])
    op.create_index("idx_user_polygons_geometry", "user_polygons", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("idx_user_polygons_geometry", table_name="user_polygons", postgresql_using="gist")
    op.drop_index("idx_user_polygons_created_at", table_name="user_polygons")
    op.drop_index("idx_user_polygons_uuid", table_name="user_polygons")
    op.drop_table("user_polygons")


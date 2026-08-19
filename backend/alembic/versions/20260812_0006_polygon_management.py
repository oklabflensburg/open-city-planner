"""add polygon management fields and user roles

Revision ID: 20260812_0006
Revises: 20260812_0005
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260812_0006"
down_revision: str | None = "20260812_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )

    columns = (
        sa.Column("floor", sa.String(length=16), nullable=True),
        sa.Column("address_display_name", sa.Text(), nullable=True),
        sa.Column("address_street", sa.String(length=160), nullable=True),
        sa.Column("address_house_number", sa.String(length=40), nullable=True),
        sa.Column("address_postal_code", sa.String(length=32), nullable=True),
        sa.Column("address_city", sa.String(length=120), nullable=True),
        sa.Column("address_country", sa.String(length=120), nullable=True),
        sa.Column("address_lookup_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=True),
        sa.Column("owner_street", sa.String(length=160), nullable=True),
        sa.Column("owner_house_number", sa.String(length=40), nullable=True),
        sa.Column("owner_postal_code", sa.String(length=32), nullable=True),
        sa.Column("owner_city", sa.String(length=120), nullable=True),
        sa.Column("owner_country", sa.String(length=120), nullable=True),
        sa.Column("price_per_sqm", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    for column in columns:
        op.add_column("user_polygons", column)
    op.create_index(
        "idx_user_polygons_updated_by_user_id", "user_polygons", ["updated_by_user_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_user_polygons_updated_by_user_id", table_name="user_polygons")
    for name in (
        "price_per_sqm",
        "owner_country",
        "owner_city",
        "owner_postal_code",
        "owner_house_number",
        "owner_street",
        "owner_name",
        "address_lookup_status",
        "address_country",
        "address_city",
        "address_postal_code",
        "address_house_number",
        "address_street",
        "address_display_name",
        "floor",
    ):
        op.drop_column("user_polygons", name)
    op.drop_column("users", "roles")

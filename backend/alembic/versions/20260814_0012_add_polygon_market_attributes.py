"""add public polygon market attributes

Revision ID: 20260814_0012
Revises: 20260814_0011
"""

import sqlalchemy as sa

from alembic import op

revision = "20260814_0012"
down_revision = "20260814_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_polygons",
        sa.Column("occupancy_status", sa.String(length=16), server_default="UNKNOWN", nullable=False),
    )
    op.add_column(
        "user_polygons",
        sa.Column("business_structure", sa.String(length=16), server_default="UNKNOWN", nullable=False),
    )
    op.create_check_constraint(
        "ck_user_polygons_occupancy_status",
        "user_polygons",
        "occupancy_status IN ('OCCUPIED', 'VACANT', 'UNKNOWN')",
    )
    op.create_check_constraint(
        "ck_user_polygons_business_structure",
        "user_polygons",
        "business_structure IN ('CHAIN', 'INDEPENDENT', 'UNKNOWN')",
    )
    op.create_index("idx_user_polygons_occupancy_status", "user_polygons", ["occupancy_status"])
    op.create_index("idx_user_polygons_business_structure", "user_polygons", ["business_structure"])


def downgrade() -> None:
    op.drop_index("idx_user_polygons_business_structure", table_name="user_polygons")
    op.drop_index("idx_user_polygons_occupancy_status", table_name="user_polygons")
    op.drop_constraint("ck_user_polygons_business_structure", "user_polygons", type_="check")
    op.drop_constraint("ck_user_polygons_occupancy_status", "user_polygons", type_="check")
    op.drop_column("user_polygons", "business_structure")
    op.drop_column("user_polygons", "occupancy_status")

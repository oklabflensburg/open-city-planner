"""Test fixture: create example B module table after dependency A."""

import sqlalchemy as sa

from alembic import op

revision = "mod_example_b_20260825_0001"
down_revision = "mod_example_a_20260825_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS example_b")
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="example_b",
    )


def downgrade() -> None:
    op.drop_table("items", schema="example_b")
    op.execute("DROP SCHEMA example_b")

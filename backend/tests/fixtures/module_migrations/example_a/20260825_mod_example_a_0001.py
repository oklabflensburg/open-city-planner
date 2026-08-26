"""Test fixture: create example A module table."""

import sqlalchemy as sa

from alembic import op

revision = "mod_example_a_20260825_0001"
down_revision = "20260825_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS example_a")
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="example_a",
    )


def downgrade() -> None:
    op.drop_table("items", schema="example_a")
    op.execute("DROP SCHEMA example_a")

"""Test fixture: fail example B migration after dependency A."""

from alembic import op

revision = "mod_example_b_20260825_0001"
down_revision = "mod_example_a_20260825_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("THIS IS NOT VALID SQL")


def downgrade() -> None:
    pass

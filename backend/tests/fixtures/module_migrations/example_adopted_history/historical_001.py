"""Historical revision adopted from the host by the fixture module."""

import sqlalchemy as sa

from alembic import op

revision = "historical_001"
down_revision = "20260825_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS example_adopted_module")
    op.create_table(
        "migration_markers",
        sa.Column("revision", sa.String(length=80), primary_key=True),
        schema="example_adopted_module",
    )
    op.execute(
        "INSERT INTO example_adopted_module.migration_markers (revision) "
        "VALUES ('historical_001')"
    )


def downgrade() -> None:
    op.drop_table("migration_markers", schema="example_adopted_module")
    op.execute("DROP SCHEMA example_adopted_module")

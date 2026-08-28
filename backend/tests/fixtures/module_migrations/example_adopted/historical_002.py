"""Second historical revision retained byte-for-byte in graph identity."""

from alembic import op

revision = "historical_002"
down_revision = "historical_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO example_adopted_module.migration_markers (revision) "
        "VALUES ('historical_002')"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM example_adopted_module.migration_markers "
        "WHERE revision = 'historical_002'"
    )

"""First newly namespaced revision after the adopted history."""

from alembic import op

revision = "mod_example_adopted_module_0001"
down_revision = "historical_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO example_adopted_module.migration_markers (revision) "
        "VALUES ('mod_example_adopted_module_0001')"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM example_adopted_module.migration_markers "
        "WHERE revision = 'mod_example_adopted_module_0001'"
    )

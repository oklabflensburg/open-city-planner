"""track typed account deactivation reasons

Revision ID: 20260817_0020
Revises: 20260816_0019
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260817_0020"
down_revision = "20260816_0019"
branch_labels = None
depends_on = None

deactivation_reason = postgresql.ENUM(
    "SELF_DEACTIVATED",
    "ADMIN_DEACTIVATED",
    name="account_deactivation_reason",
    create_type=False,
)


def upgrade() -> None:
    deactivation_reason.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("deactivation_reason", deactivation_reason))
    op.execute(
        sa.text(
            """
            UPDATE users
            SET deactivated_at = updated_at,
                deactivation_reason = 'ADMIN_DEACTIVATED'
            WHERE is_active = false
            """
        )
    )


def downgrade() -> None:
    op.drop_column("users", "deactivation_reason")
    op.drop_column("users", "deactivated_at")
    deactivation_reason.drop(op.get_bind(), checkfirst=True)

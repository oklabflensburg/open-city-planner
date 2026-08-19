"""security hardening state

Revision ID: 20260819_0028
Revises: 20260819_0027
"""

import sqlalchemy as sa

from alembic import op

revision = "20260819_0028"
down_revision = "20260819_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "password_reset_tokens",
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "invalidated_at")

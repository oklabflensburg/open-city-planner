"""verify users with matching provider emails

Revision ID: 20260812_0004
Revises: 20260811_0003
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_0004"
down_revision: str | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET is_verified = true,
                updated_at = CURRENT_TIMESTAMP
            WHERE is_verified = false
              AND EXISTS (
                  SELECT 1
                  FROM user_oauth_accounts
                  WHERE user_oauth_accounts.user_id = users.id
                    AND user_oauth_accounts.provider_email IS NOT NULL
                    AND lower(trim(user_oauth_accounts.provider_email)) = lower(trim(users.email))
              )
            """
        )
    )


def downgrade() -> None:
    # Verification cannot be safely undone because the previous state is not retained.
    pass

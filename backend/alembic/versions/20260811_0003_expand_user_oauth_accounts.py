"""expand user oauth accounts

Revision ID: 20260811_0003
Revises: 20260811_0002
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0003"
down_revision: str | None = "20260811_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("user_oauth_accounts", "provider", existing_type=sa.String(length=80), type_=sa.String(length=50), existing_nullable=False)
    op.add_column("user_oauth_accounts", sa.Column("provider_username", sa.String(length=255), nullable=True))
    op.add_column("user_oauth_accounts", sa.Column("provider_avatar_url", sa.Text(), nullable=True))
    op.add_column("user_oauth_accounts", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_oauth_provider_subject", "user_oauth_accounts", type_="unique")
    op.create_unique_constraint("uq_user_oauth_accounts_provider_subject", "user_oauth_accounts", ["provider", "provider_subject"])
    op.create_unique_constraint("uq_user_oauth_accounts_user_provider", "user_oauth_accounts", ["user_id", "provider"])
    op.create_index("idx_user_oauth_accounts_provider", "user_oauth_accounts", ["provider"])


def downgrade() -> None:
    op.drop_index("idx_user_oauth_accounts_provider", table_name="user_oauth_accounts")
    op.drop_constraint("uq_user_oauth_accounts_user_provider", "user_oauth_accounts", type_="unique")
    op.drop_constraint("uq_user_oauth_accounts_provider_subject", "user_oauth_accounts", type_="unique")
    op.create_unique_constraint("uq_oauth_provider_subject", "user_oauth_accounts", ["provider", "provider_subject"])
    op.drop_column("user_oauth_accounts", "last_login_at")
    op.drop_column("user_oauth_accounts", "provider_avatar_url")
    op.drop_column("user_oauth_accounts", "provider_username")
    op.alter_column("user_oauth_accounts", "provider", existing_type=sa.String(length=50), type_=sa.String(length=80), existing_nullable=False)

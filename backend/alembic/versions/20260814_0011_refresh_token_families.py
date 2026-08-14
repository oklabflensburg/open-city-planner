"""add refresh-token family and rotation metadata

Revision ID: 20260814_0011
Revises: 20260813_0010
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260814_0011"
down_revision: str | None = "20260813_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("user_sessions", sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_sessions", sa.Column("replaced_by_jti", sa.String(length=64), nullable=True))
    op.add_column("user_sessions", sa.Column("revocation_reason", sa.String(length=80), nullable=True))
    op.execute("UPDATE user_sessions SET family_id = id WHERE family_id IS NULL")
    op.alter_column("user_sessions", "family_id", nullable=False)
    op.create_index("idx_user_sessions_family_id", "user_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_index("idx_user_sessions_family_id", table_name="user_sessions")
    op.drop_column("user_sessions", "revocation_reason")
    op.drop_column("user_sessions", "replaced_by_jti")
    op.drop_column("user_sessions", "rotated_at")
    op.drop_column("user_sessions", "family_id")

"""add TOTP MFA methods, recovery codes and login challenges

Revision ID: 20260819_0026
Revises: 20260818_0025
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260819_0026"
down_revision = "20260818_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_mfa_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(32), nullable=False, server_default="totp"),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("setup_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_counter", sa.BigInteger()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_user_mfa_methods_totp_user",
        "user_mfa_methods",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("type = 'totp'"),
    )
    op.create_index("idx_user_mfa_methods_enabled", "user_mfa_methods", ["user_id", "is_enabled"])
    op.create_table(
        "user_mfa_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_user_mfa_recovery_codes_user_unused", "user_mfa_recovery_codes", ["user_id", "used_at"]
    )
    op.create_table(
        "auth_mfa_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("purpose", sa.String(32), nullable=False, server_default="login"),
        sa.Column("primary_method", sa.String(32), nullable=False),
        sa.Column("redirect_path", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("user_agent", sa.Text()),
    )
    op.create_index("idx_auth_mfa_challenges_user", "auth_mfa_challenges", ["user_id"])
    op.create_index("idx_auth_mfa_challenges_expires", "auth_mfa_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_mfa_challenges")
    op.drop_table("user_mfa_recovery_codes")
    op.drop_table("user_mfa_methods")

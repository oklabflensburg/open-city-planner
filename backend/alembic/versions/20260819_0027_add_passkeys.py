"""add WebAuthn credentials and ceremony challenges

Revision ID: 20260819_0027
Revises: 20260819_0026
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260819_0027"
down_revision = "20260819_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_webauthn_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("aaguid", postgresql.UUID(as_uuid=True)),
        sa.Column("transports", postgresql.JSONB()),
        sa.Column("device_type", sa.String(32)),
        sa.Column("backed_up", sa.Boolean()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_user_webauthn_credentials_user", "user_webauthn_credentials", ["user_id"]
    )
    op.create_table(
        "webauthn_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "mfa_challenge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_mfa_challenges.id", ondelete="CASCADE"),
        ),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("challenge", sa.LargeBinary(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
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
    op.create_index("idx_webauthn_challenges_user", "webauthn_challenges", ["user_id"])
    op.create_index("idx_webauthn_challenges_expires", "webauthn_challenges", ["expires_at"])


def downgrade() -> None:
    op.drop_table("webauthn_challenges")
    op.drop_table("user_webauthn_credentials")

"""add federated Mastodon SSO identities and instance credentials

Revision ID: 20260816_0019
Revises: 20260816_0018
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260816_0019"
down_revision = "20260816_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(sa.text("""
        UPDATE users
        SET email = split_part(email, '@', 1) || '@pending.stadtplaner.oklabflensburg.de',
            email_pending = true
        WHERE email LIKE '%@oauth.local'
    """))
    op.drop_constraint(
        "uq_user_oauth_accounts_provider_subject",
        "user_oauth_accounts",
        type_="unique",
    )
    op.add_column(
        "user_oauth_accounts",
        sa.Column("provider_instance", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user_oauth_accounts",
        sa.Column("provider_profile_url", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_user_oauth_accounts_central_identity",
        "user_oauth_accounts",
        ["provider", "provider_subject"],
        unique=True,
        postgresql_where=sa.text("provider_instance IS NULL"),
    )
    op.create_index(
        "uq_user_oauth_accounts_federated_identity",
        "user_oauth_accounts",
        ["provider", "provider_instance", "provider_subject"],
        unique=True,
        postgresql_where=sa.text("provider_instance IS NOT NULL"),
    )

    op.create_table(
        "mastodon_oauth_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instance_origin", sa.String(length=255), nullable=False, unique=True),
        sa.Column("client_id_encrypted", sa.Text(), nullable=True),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("oauth_scope", sa.String(length=64), nullable=True),
        sa.Column("software_version", sa.String(length=120), nullable=True),
        sa.Column("registration_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("registration_retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "oauth_flow_grants",
        sa.Column("state_hash", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("redirect_path", sa.Text(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("instance_origin", sa.String(length=255), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("mode IN ('login','link')", name="ck_oauth_flow_grants_mode"),
    )
    op.create_index("idx_oauth_flow_grants_expires_at", "oauth_flow_grants", ["expires_at"])


def downgrade() -> None:
    op.drop_table("oauth_flow_grants")
    op.drop_table("mastodon_oauth_instances")
    op.drop_index("uq_user_oauth_accounts_federated_identity", table_name="user_oauth_accounts")
    op.drop_index("uq_user_oauth_accounts_central_identity", table_name="user_oauth_accounts")
    op.drop_column("user_oauth_accounts", "provider_profile_url")
    op.drop_column("user_oauth_accounts", "provider_instance")
    op.create_unique_constraint(
        "uq_user_oauth_accounts_provider_subject",
        "user_oauth_accounts",
        ["provider", "provider_subject"],
    )
    op.drop_column("users", "email_pending")

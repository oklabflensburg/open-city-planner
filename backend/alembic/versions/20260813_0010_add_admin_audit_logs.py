"""add audit log for security-relevant administration changes

Revision ID: 20260813_0010
Revises: 20260813_0009
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260813_0010"
down_revision = "20260813_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_admin_audit_logs_actor", "admin_audit_logs", ["actor_user_id"])
    op.create_index("idx_admin_audit_logs_target", "admin_audit_logs", ["target_user_id"])
    op.create_index("idx_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("idx_admin_audit_logs_target", table_name="admin_audit_logs")
    op.drop_index("idx_admin_audit_logs_actor", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")

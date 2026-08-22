"""Add polygon outbox

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-22 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260822_0033'
down_revision = '20260819_0032'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('user_polygons', sa.Column('idempotency_key', sa.String(length=255), nullable=True))
    op.create_unique_constraint('uq_user_polygons_idempotency_key', 'user_polygons', ['idempotency_key'])
    op.create_table(
        'polygon_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('polygon_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='PENDING', nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('PENDING','PROCESSING','COMPLETED','FAILED','DEAD_LETTER')", name='ck_polygon_outbox_status')
    )
    op.create_index('idx_polygon_outbox_due', 'polygon_outbox', ['status', 'next_attempt_at'], unique=False)

def downgrade() -> None:
    op.drop_index('idx_polygon_outbox_due', table_name='polygon_outbox')
    op.drop_table('polygon_outbox')
    op.drop_constraint('uq_user_polygons_idempotency_key', 'user_polygons', type_='unique')
    op.drop_column('user_polygons', 'idempotency_key')

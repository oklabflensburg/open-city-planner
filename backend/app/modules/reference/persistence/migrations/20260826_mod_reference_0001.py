"""Create and seed the reference module's owned items table."""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "mod_reference_20260826_0001"
down_revision = "20260825_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS reference")
    op.create_table(
        "items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="reference",
    )
    items = sa.table(
        "items",
        sa.column("id", sa.String()),
        sa.column("title", sa.String()),
        sa.column("description", sa.String()),
        sa.column("longitude", sa.Float()),
        sa.column("latitude", sa.Float()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        schema="reference",
    )
    op.bulk_insert(
        items,
        [
            {
                "id": "4fbc9831-0d31-4a8a-963b-111111111111",
                "title": "Referenzmarker Hafen",
                "description": "Beispieldatensatz des installierbaren Referenzmoduls.",
                "longitude": 9.4338,
                "latitude": 54.7952,
                "created_at": datetime(2026, 8, 26, tzinfo=UTC),
            },
            {
                "id": "4fbc9831-0d31-4a8a-963b-222222222222",
                "title": "Referenzmarker Innenstadt",
                "description": "Zeigt den Weg von der Modultabelle bis zur Karte.",
                "longitude": 9.4362,
                "latitude": 54.7836,
                "created_at": datetime(2026, 8, 26, tzinfo=UTC),
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("items", schema="reference")
    op.execute("DROP SCHEMA reference")

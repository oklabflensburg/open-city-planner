"""add persistent polygon slugs

Revision ID: 20260812_0005
Revises: 20260812_0004
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_0005"
down_revision: str | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_polygons", sa.Column("slug", sa.String(length=255), nullable=True))
    op.execute(
        """
        WITH normalized AS (
            SELECT id,
                   uuid,
                   left(trim(both '-' from regexp_replace(
                       replace(
                           replace(
                               replace(
                                   replace(lower(name), 'ä', 'ae'),
                                   'ö', 'oe'
                               ),
                               'ü', 'ue'
                           ),
                           'ß', 'ss'
                       ),
                       '[^a-z0-9]+', '-', 'g'
                   )), 240) AS candidate
            FROM user_polygons
        ), based AS (
            SELECT id,
                   CASE
                       WHEN candidate = '' THEN 'flaeche-' || left(uuid::text, 8)
                       ELSE candidate
                   END AS base
            FROM normalized
        ), numbered AS (
            SELECT id,
                   base,
                   row_number() OVER (PARTITION BY base ORDER BY id) AS occurrence
            FROM based
        )
        UPDATE user_polygons AS polygon
        SET slug = CASE
            WHEN numbered.occurrence = 1 THEN numbered.base
            ELSE numbered.base || '-' || numbered.occurrence::text
        END
        FROM numbered
        WHERE polygon.id = numbered.id
        """
    )
    op.alter_column("user_polygons", "slug", nullable=False)
    op.create_unique_constraint("uq_user_polygons_slug", "user_polygons", ["slug"])


def downgrade() -> None:
    op.drop_constraint("uq_user_polygons_slug", "user_polygons", type_="unique")
    op.drop_column("user_polygons", "slug")

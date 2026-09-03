#!/usr/bin/env python3
"""Prove the planned external Analysis Areas -> polygon-port consumer boundary."""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.discovery import activate_enabled_module_python_paths
from app.platform.modules.sdk import PolygonQueryPort, PolygonScope


def parse_args() -> argparse.Namespace:
    return argparse.ArgumentParser().parse_args()


async def module_owned_polygon_scope(
    session: AsyncSession, area_id: UUID
) -> PolygonScope | None:
    """Model the future consumer using only module-owned persistence models."""

    from ocp_module_analysis_areas.persistence.models import (
        AnalysisArea,
        PolygonAnalysisArea,
    )

    area_db_id = await session.scalar(
        select(AnalysisArea.id).where(AnalysisArea.uuid == area_id)
    )
    if area_db_id is None:
        return None
    polygon_ids = await session.scalars(
        select(PolygonAnalysisArea.polygon_id).where(
            PolygonAnalysisArea.analysis_area_id == area_db_id
        )
    )
    return PolygonScope(tuple(polygon_ids))


class _ScalarValues:
    def __iter__(self):
        return iter((7, 11))


class _ContractSession:
    statements: list[str]

    def __init__(self) -> None:
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(str(statement))
        return 23

    async def scalars(self, statement):
        self.statements.append(str(statement))
        return _ScalarValues()


class _PolygonConsumer:
    async def list_by_scope(
        self, session: AsyncSession, scope: PolygonScope, *, limit: int
    ) -> tuple[object, ...]:
        assert session is not None
        assert scope == PolygonScope((7, 11))
        assert limit == 25
        return ()


async def check() -> None:
    activate_enabled_module_python_paths()
    session = _ContractSession()
    scope = await module_owned_polygon_scope(  # type: ignore[arg-type]
        session, UUID("b0773da4-4782-4dca-8d49-d2db77bba055")
    )
    assert scope == PolygonScope((7, 11))
    assert "analysis_areas" in session.statements[0]
    assert "polygon_analysis_areas" in session.statements[1]
    assert "user_polygons" not in " ".join(session.statements)

    polygons: PolygonQueryPort = _PolygonConsumer()  # type: ignore[assignment]
    await polygons.list_by_scope(session, scope, limit=25)  # type: ignore[arg-type]


def main() -> int:
    parse_args()
    asyncio.run(check())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

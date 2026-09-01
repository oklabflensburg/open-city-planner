import ast
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import get_type_hints

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.integrations.module_host_ports import HostPolygonAssignments
from app.models.user import User
from app.models.user_polygon import UserPolygon
from app.modules.analysis_areas.persistence.models import AnalysisArea, PolygonAnalysisArea
from app.platform.events import InProcessEventBus
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    POLYGON_ASSIGNMENT_SERVICE_ID,
    POLYGON_ASSIGNMENT_SERVICE_VERSION,
    PolygonAssignmentArea,
    PolygonAssignmentPort,
    PolygonAssignmentRequest,
    PolygonAssignmentResult,
)
from app.platform.modules.testing import FakePolygonAssignments, create_test_module_context
from tests.fixtures.polygon_assignment_contract_module import (
    DEFINITION,
    PolygonAssignmentContractConsumerModule,
)
from tests.test_module_runtime import FakeDiscovery

AREA_A = "11111111-1111-4111-8111-111111111111"
AREA_B = "22222222-2222-4222-8222-222222222222"
COVERING = "POLYGON((9.3 54.3,9.7 54.3,9.7 54.7,9.3 54.7,9.3 54.3))"
SMALL_COVERING = "POLYGON((9.35 54.35,9.6 54.35,9.6 54.6,9.35 54.6,9.35 54.35))"
AWAY = "POLYGON((10.0 55.0,10.2 55.0,10.2 55.2,10.0 55.2,10.0 55.0))"


def test_assignment_dtos_are_immutable_validated_and_orm_free() -> None:
    area = PolygonAssignmentArea(AREA_A, "district", b"geometry")
    request = PolygonAssignmentRequest((area,))

    with pytest.raises(AttributeError):
        area.external_id = AREA_B  # type: ignore[misc]
    with pytest.raises(ValueError, match="UUID"):
        PolygonAssignmentArea("area-a", "district", b"geometry")
    with pytest.raises(ValueError, match="unique"):
        PolygonAssignmentRequest((area, area))

    rendered_hints = repr(
        {
            cls.__name__: get_type_hints(cls)
            for cls in (
                PolygonAssignmentArea,
                PolygonAssignmentRequest,
                PolygonAssignmentResult,
            )
        }
    ).lower()
    assert "sqlalchemy" not in rendered_hints
    assert "app.models" not in rendered_hints
    assert "app.db" not in rendered_hints
    assert request.areas == (area,)


@pytest.mark.asyncio
async def test_test_context_exposes_recording_assignment_fake() -> None:
    context = create_test_module_context()
    assert context.services is not None
    service = context.services.require(
        PolygonAssignmentPort,
        service_id=POLYGON_ASSIGNMENT_SERVICE_ID,
        version=POLYGON_ASSIGNMENT_SERVICE_VERSION,
    )
    assert isinstance(service, FakePolygonAssignments)

    request = PolygonAssignmentRequest(())
    result = await service.refresh_assignments(object(), request)  # type: ignore[arg-type]

    assert service.calls == [request]
    assert result == PolygonAssignmentResult(0, 0, 0, 0, 0)


def test_external_fixture_uses_only_sdk_and_adapter_is_consumer_neutral() -> None:
    source_path = Path(__file__).parent / "fixtures" / "polygon_assignment_contract_module.py"
    tree = ast.parse(source_path.read_text())
    app_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
    }
    assert app_imports == {"app.platform.modules.sdk"}

    adapter_source = Path(__file__).parents[1] / "app" / "integrations" / "module_host_ports.py"
    host_adapter = ast.get_source_segment(
        adapter_source.read_text(),
        next(
            node
            for node in ast.walk(ast.parse(adapter_source.read_text()))
            if isinstance(node, ast.ClassDef) and node.name == "HostPolygonAssignments"
        ),
    )
    assert host_adapter is not None
    assert "analysis-areas" not in host_adapter.lower()
    assert "analysis_areas" not in host_adapter.lower()


def _consumer() -> PolygonAssignmentContractConsumerModule:
    factory = ModuleContextFactory(
        ModuleHostServices(polygon_assignments=HostPolygonAssignments()),
        event_bus=InProcessEventBus(),
    )
    runtime = create_module_runtime(
        enabled_module_ids=(DEFINITION.declared_id,),
        discovery_providers=(FakeDiscovery([DEFINITION]),),
        host_version="0.2.0",
        context_factory=factory,
    )
    runtime.register(FastAPI())
    consumer = runtime.registry.get(DEFINITION.declared_id).module
    assert isinstance(consumer, PolygonAssignmentContractConsumerModule)
    return consumer


@pytest_asyncio.fixture
async def assignment_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = make_url(get_settings().database_url).set(database="postgres")
    schema = f"test_polygon_assignment_{uuid.uuid4().hex}"
    admin = create_async_engine(url)
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except (ConnectionError, DBAPIError, OSError, OperationalError) as exc:
        await admin.dispose()
        pytest.skip(f"PostgreSQL/PostGIS is unavailable: {type(exc).__name__}")
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": f"{schema},public"}}
    )
    tables = [
        User.__table__,
        UserPolygon.__table__,
        AnalysisArea.__table__,
        PolygonAnalysisArea.__table__,
    ]
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection, tables=tables
                )
            )
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def _ewkb(session: AsyncSession, geometry: str) -> bytes:
    value = await session.scalar(
        text("SELECT ST_AsEWKB(ST_Multi(ST_GeomFromText(:geometry, 4326)))"),
        {"geometry": geometry},
    )
    assert value is not None
    return bytes(value)


async def _seed(session: AsyncSession) -> None:
    await session.execute(
        text("""
INSERT INTO analysis_areas
  (uuid, slug, name, area_type, geometry, centroid, area_m2, source,
   wikidata_verified, created_at, updated_at)
VALUES
  (:area_a, 'area-a', 'Area A', 'DISTRICT',
   ST_Multi(ST_GeomFromText(:covering, 4326)), ST_Point(9.5, 54.5, 4326), 1,
   'MANUAL', false, now(), now()),
  (:area_b, 'area-b', 'Area B', 'DISTRICT',
   ST_Multi(ST_GeomFromText(:away, 4326)), ST_Point(10.1, 55.1, 4326), 1,
   'MANUAL', false, now(), now())
"""),
        {
            "area_a": AREA_A,
            "area_b": AREA_B,
            "covering": COVERING,
            "away": AWAY,
        },
    )
    await session.execute(
        text("""
INSERT INTO user_polygons
  (uuid, name, slug, address_lookup_status, occupancy_status, occupancy_source,
   business_structure, category, geometry, properties, created_at, updated_at)
VALUES
  (:polygon_id, 'Polygon', 'polygon', 'pending', 'UNKNOWN', 'UNKNOWN',
   'UNKNOWN', 'custom', ST_GeomFromText(
     'POLYGON((9.4 54.4,9.5 54.4,9.5 54.5,9.4 54.5,9.4 54.4))', 4326
   ), '{}'::jsonb, now(), now())
"""),
        {
            "polygon_id": str(uuid.uuid4()),
        },
    )
    await session.commit()


async def _assigned_external_ids(session: AsyncSession) -> tuple[str, ...]:
    rows = await session.scalars(
        text("""
SELECT area.uuid::text
FROM polygon_analysis_areas assignment
JOIN analysis_areas area ON area.id = assignment.analysis_area_id
ORDER BY area.uuid
""")
    )
    return tuple(rows)


@pytest.mark.asyncio
async def test_external_consumer_assigns_real_polygons_with_historical_selection(
    assignment_sessions,
) -> None:
    consumer = _consumer()
    async with assignment_sessions() as session:
        await _seed(session)
        request = PolygonAssignmentRequest(
            (
                PolygonAssignmentArea(AREA_A, "district", await _ewkb(session, COVERING)),
                PolygonAssignmentArea(
                    AREA_B, "district", await _ewkb(session, SMALL_COVERING)
                ),
            )
        )
        result = await consumer.refresh(session, request)
        await session.commit()

        assert result == PolygonAssignmentResult(1, 1, 0, 0, 0)
        assert await _assigned_external_ids(session) == (AREA_B,)


@pytest.mark.asyncio
async def test_geometry_update_is_idempotent_and_empty_snapshot_removes_stale_state(
    assignment_sessions,
) -> None:
    consumer = _consumer()
    async with assignment_sessions() as session:
        await _seed(session)
        initial = PolygonAssignmentRequest(
            (PolygonAssignmentArea(AREA_A, "district", await _ewkb(session, COVERING)),)
        )
        assert (await consumer.refresh(session, initial)).created_assignments == 1
        changed = PolygonAssignmentRequest(
            (
                PolygonAssignmentArea(AREA_A, "district", await _ewkb(session, AWAY)),
                PolygonAssignmentArea(AREA_B, "district", await _ewkb(session, COVERING)),
            )
        )
        first = await consumer.refresh(session, changed)
        second = await consumer.refresh(session, changed)

        assert first.created_assignments == 1
        assert first.removed_assignments == 1
        assert second == PolygonAssignmentResult(1, 0, 0, 0, 1)
        assert await _assigned_external_ids(session) == (AREA_B,)

        removed = await consumer.refresh(session, PolygonAssignmentRequest(()))
        assert removed.removed_assignments == 1
        assert await _assigned_external_ids(session) == ()


@pytest.mark.asyncio
async def test_assignment_and_caller_owned_area_write_roll_back_together(
    assignment_sessions,
) -> None:
    consumer = _consumer()
    async with assignment_sessions() as session:
        await _seed(session)
        initial = PolygonAssignmentRequest(
            (PolygonAssignmentArea(AREA_A, "district", await _ewkb(session, COVERING)),)
        )
        await consumer.refresh(session, initial)
        await session.commit()

        await session.execute(
            text("UPDATE analysis_areas SET name='Changed' WHERE uuid=:area_a"),
            {"area_a": AREA_A},
        )
        changed = PolygonAssignmentRequest(
            (PolygonAssignmentArea(AREA_B, "district", await _ewkb(session, COVERING)),)
        )
        await consumer.refresh(session, changed)
        await session.rollback()

        assert await _assigned_external_ids(session) == (AREA_A,)
        assert await session.scalar(
            text("SELECT name FROM analysis_areas WHERE uuid=:area_a"),
            {"area_a": AREA_A},
        ) == "Area A"

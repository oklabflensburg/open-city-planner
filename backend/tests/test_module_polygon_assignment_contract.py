import ast
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import get_type_hints
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.integrations import module_host_ports
from app.integrations.module_host_ports import HostPolygonSpatialMatches
from app.models.user import User
from app.models.user_polygon import UserPolygon
from app.platform.events import InProcessEventBus
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    POLYGON_SPATIAL_MATCH_SERVICE_ID,
    POLYGON_SPATIAL_MATCH_SERVICE_VERSION,
    PolygonSpatialArea,
    PolygonSpatialMatch,
    PolygonSpatialMatchPort,
    PolygonSpatialMatchRequest,
    PolygonSpatialMatchResult,
)
from app.platform.modules.testing import (
    FakePolygonSpatialMatches,
    create_test_module_context,
)
from tests.fixtures.polygon_assignment_contract_module import (
    DEFINITION,
    PolygonSpatialMatchContractConsumerModule,
)
from tests.test_module_runtime import FakeDiscovery

POLYGON_ID = "33333333-3333-4333-8333-333333333333"
COVERING = "POLYGON((9.3 54.3,9.7 54.3,9.7 54.7,9.3 54.7,9.3 54.3))"
SMALL_COVERING = "POLYGON((9.35 54.35,9.6 54.35,9.6 54.6,9.35 54.6,9.35 54.35))"
AWAY = "POLYGON((10.0 55.0,10.2 55.0,10.2 55.2,10.0 55.2,10.0 55.0))"


def test_spatial_match_dtos_are_immutable_validated_and_orm_free() -> None:
    area = PolygonSpatialArea("consumer:district", "district", b"geometry")
    request = PolygonSpatialMatchRequest((area,))
    match = PolygonSpatialMatch(POLYGON_ID, area.external_id, area.selection_group, 0.5)

    with pytest.raises(AttributeError):
        area.external_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="normalized"):
        PolygonSpatialArea(" area ", "district", b"geometry")
    with pytest.raises(ValueError, match="unique"):
        PolygonSpatialMatchRequest((area, area))

    rendered_hints = repr(
        {
            cls.__name__: get_type_hints(cls)
            for cls in (
                PolygonSpatialArea,
                PolygonSpatialMatch,
                PolygonSpatialMatchRequest,
                PolygonSpatialMatchResult,
            )
        }
    ).lower()
    assert "sqlalchemy" not in rendered_hints
    assert "app.models" not in rendered_hints
    assert "app.db" not in rendered_hints
    assert request.areas == (area,)
    assert match.polygon_id == POLYGON_ID


@pytest.mark.asyncio
async def test_test_context_exposes_recording_spatial_match_fake() -> None:
    context = create_test_module_context()
    assert context.services is not None
    service = context.services.require(
        PolygonSpatialMatchPort,
        service_id=POLYGON_SPATIAL_MATCH_SERVICE_ID,
        version=POLYGON_SPATIAL_MATCH_SERVICE_VERSION,
    )
    assert isinstance(service, FakePolygonSpatialMatches)

    request = PolygonSpatialMatchRequest(())
    result = await service.match_polygons(object(), request)  # type: ignore[arg-type]

    assert service.calls == [request]
    assert result == PolygonSpatialMatchResult(())


@pytest.mark.asyncio
async def test_adapter_is_thin_read_only_and_consumer_neutral(monkeypatch) -> None:
    expected = PolygonSpatialMatchResult(())
    query = AsyncMock(return_value=expected)
    monkeypatch.setattr(module_host_ports, "match_user_polygons", query)
    session = AsyncMock()
    request = PolygonSpatialMatchRequest(())

    assert await HostPolygonSpatialMatches().match_polygons(session, request) is expected
    query.assert_awaited_once_with(session, request)
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()

    root = Path(__file__).parents[1]
    production_sources = (
        root / "app" / "services" / "polygon_spatial_matches.py",
        root / "app" / "integrations" / "module_host_ports.py",
        root / "app" / "platform" / "modules" / "sdk.py",
    )
    adapter_source = (root / "app" / "integrations" / "module_host_ports.py").read_text()
    adapter_tree = ast.parse(adapter_source)
    adapter_class = ast.get_source_segment(
        adapter_source,
        next(
            node
            for node in ast.walk(adapter_tree)
            if isinstance(node, ast.ClassDef) and node.name == "HostPolygonSpatialMatches"
        ),
    )
    assert adapter_class is not None
    for source in production_sources:
        lowered = source.read_text().lower()
        assert "analysis_areas" not in lowered
        assert "analysis-area" not in lowered
        assert "analysis_area" not in lowered
        assert "polygon_analysis_areas" not in lowered
    assert "commit(" not in (root / "app" / "services" / "polygon_spatial_matches.py").read_text()
    assert "rollback(" not in (root / "app" / "services" / "polygon_spatial_matches.py").read_text()


def test_external_fixture_uses_only_public_sdk() -> None:
    source_path = Path(__file__).parent / "fixtures" / "polygon_assignment_contract_module.py"
    tree = ast.parse(source_path.read_text())
    app_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
    }
    assert app_imports == {"app.platform.modules.sdk"}


def _consumer() -> PolygonSpatialMatchContractConsumerModule:
    factory = ModuleContextFactory(
        ModuleHostServices(polygon_spatial_matches=HostPolygonSpatialMatches()),
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
    assert isinstance(consumer, PolygonSpatialMatchContractConsumerModule)
    return consumer


@pytest_asyncio.fixture
async def spatial_match_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = make_url(get_settings().database_url).set(database="postgres")
    schema = f"test_polygon_spatial_match_{uuid.uuid4().hex}"
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
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[User.__table__, UserPolygon.__table__],
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
INSERT INTO user_polygons
  (uuid, name, slug, address_lookup_status, occupancy_status, occupancy_source,
   business_structure, category, geometry, properties, created_at, updated_at)
VALUES
  (:polygon_id, 'Polygon', 'polygon', 'pending', 'UNKNOWN', 'UNKNOWN',
   'UNKNOWN', 'custom', ST_GeomFromText(
     'POLYGON((9.4 54.4,9.5 54.4,9.5 54.5,9.4 54.5,9.4 54.4))', 4326
   ), '{}'::jsonb, now(), now())
"""),
        {"polygon_id": POLYGON_ID},
    )
    await session.commit()


async def _polygon_state(session: AsyncSession) -> tuple[object, ...]:
    row = (
        await session.execute(
            text("""
SELECT uuid::text, name, slug, encode(ST_AsEWKB(geometry), 'hex'), updated_at::text
FROM user_polygons
""")
        )
    ).one()
    return tuple(row)


@pytest.mark.asyncio
async def test_external_consumer_returns_smallest_match_per_group_without_area_tables(
    spatial_match_sessions,
) -> None:
    consumer = _consumer()
    async with spatial_match_sessions() as session:
        await _seed(session)
        request = PolygonSpatialMatchRequest(
            (
                PolygonSpatialArea(
                    "consumer-a:district-large",
                    "district",
                    await _ewkb(session, COVERING),
                ),
                PolygonSpatialArea(
                    "consumer-a:district-small",
                    "district",
                    await _ewkb(session, SMALL_COVERING),
                ),
                PolygonSpatialArea(
                    "consumer-a:quarter",
                    "quarter",
                    await _ewkb(session, COVERING),
                ),
                PolygonSpatialArea(
                    "consumer-a:away", "away", await _ewkb(session, AWAY)
                ),
            )
        )
        result = await consumer.match(session, request)

    assert [(item.external_area_id, item.selection_group) for item in result.matches] == [
        ("consumer-a:district-small", "district"),
        ("consumer-a:quarter", "quarter"),
    ]
    assert {item.polygon_id for item in result.matches} == {POLYGON_ID}
    assert all(
        item.overlap_ratio is not None and 0 < item.overlap_ratio <= 1
        for item in result.matches
    )


@pytest.mark.asyncio
async def test_spatial_queries_are_idempotent_and_isolated_without_mutation(
    spatial_match_sessions,
) -> None:
    consumer = _consumer()
    async with spatial_match_sessions() as session:
        await _seed(session)
        before = await _polygon_state(session)
        consumer_a = PolygonSpatialMatchRequest(
            (
                PolygonSpatialArea(
                    "consumer-a:area", "district", await _ewkb(session, COVERING)
                ),
            )
        )
        consumer_b = PolygonSpatialMatchRequest(
            (
                PolygonSpatialArea(
                    "consumer-b:area", "district", await _ewkb(session, AWAY)
                ),
            )
        )

        first = await consumer.match(session, consumer_a)
        repeated = await consumer.match(session, consumer_a)
        no_match = await consumer.match(session, consumer_b)
        after = await _polygon_state(session)

        assert first == repeated
        assert len(first.matches) == 1
        assert no_match == PolygonSpatialMatchResult(())
        assert after == before
        table_names = set(
            await session.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")
            )
        )
        assert table_names == {"users", "user_polygons"}

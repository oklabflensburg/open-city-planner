import ast
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.integrations.module_host_ports import HostOsmSnapshotQueries
from app.platform.events import InProcessEventBus
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    OSM_SNAPSHOT_QUERY_SERVICE_ID,
    OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
    OsmFeatureSnapshot,
    OsmSnapshotQuery,
    OsmSnapshotQueryPort,
    OsmTagFilter,
)
from app.platform.modules.testing import create_test_module_context
from tests.fixtures.osm_contract_module import DEFINITION
from tests.test_module_runtime import FakeDiscovery


def test_osm_snapshot_dtos_are_immutable_validated_copies() -> None:
    tags = {"boundary": "administrative"}
    snapshot = OsmFeatureSnapshot(
        osm_type="relation",
        osm_id=42,
        tags=tags,
        geometry_wkb=b"geometry",
        bbox=(9.4, 54.7, 9.5, 54.8),
        imported_at=datetime.now(UTC),
    )
    tags["name"] = "changed"

    assert snapshot.tags == MappingProxyType({"boundary": "administrative"})
    with pytest.raises(TypeError):
        snapshot.tags["name"] = "Flensburg"  # type: ignore[index]
    with pytest.raises(ValueError, match="between 1 and 500"):
        OsmSnapshotQuery(limit=501)
    with pytest.raises(ValueError, match="EPSG:4326"):
        OsmSnapshotQuery(bbox=(10.0, 55.0, 9.0, 54.0))
    with pytest.raises(ValueError, match="at most 50 unique values"):
        OsmTagFilter("place", tuple(str(value) for value in range(51)))
    with pytest.raises(ValueError, match="at most 20 unique tag filters"):
        OsmSnapshotQuery(tag_filters=tuple(OsmTagFilter(f"key-{value}") for value in range(21)))


def test_test_context_exposes_versioned_osm_fake() -> None:
    context = create_test_module_context()
    assert context.services is not None
    service = context.services.require(
        OsmSnapshotQueryPort,
        service_id=OSM_SNAPSHOT_QUERY_SERVICE_ID,
        version=OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
    )
    assert service is not None


def test_external_fixture_uses_only_sdk_and_platform_dependency() -> None:
    source_path = Path(__file__).parent / "fixtures" / "osm_contract_module.py"
    tree = ast.parse(source_path.read_text())
    app_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
    }
    assert app_imports == {"app.platform.modules.sdk"}

    factory = ModuleContextFactory(
        ModuleHostServices(osm_snapshots=HostOsmSnapshotQueries()),
        event_bus=InProcessEventBus(),
    )
    runtime = create_module_runtime(
        enabled_module_ids=(DEFINITION.declared_id,),
        discovery_providers=(FakeDiscovery([DEFINITION]),),
        host_version="0.2.0",
        context_factory=factory,
    )
    runtime.register(FastAPI())


def test_host_adapter_is_consumer_neutral_and_event_is_enqueued_before_commit() -> None:
    root = Path(__file__).parents[1]
    adapter_source = (root / "app" / "services" / "osm_snapshots.py").read_text()
    composition_source = (root / "app" / "integrations" / "module_host_ports.py").read_text()
    postprocess_source = (root / "app" / "cli" / "postprocess_osm.py").read_text()

    assert "analysis_areas" not in adapter_source + composition_source
    assert postprocess_source.index("await enqueue_osm_postprocessing_completed") < (
        postprocess_source.index('progress(verbose, started_at, "commit")')
    )


@pytest_asyncio.fixture
async def osm_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = make_url(get_settings().database_url).set(database="postgres")
    schema = f"test_osm_contract_{uuid.uuid4().hex}"
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
            await connection.execute(
                text("""
CREATE TABLE osm_features (
  osm_type text NOT NULL, osm_id bigint NOT NULL,
  geometry geometry(Geometry, 4326) NOT NULL,
  tags jsonb NOT NULL, imported_at timestamptz NOT NULL,
  PRIMARY KEY (osm_type, osm_id)
)
""")
            )
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.mark.asyncio
async def test_snapshot_query_filters_and_paginates_stably(osm_sessions) -> None:
    imported_at = datetime(2026, 8, 31, 12, tzinfo=UTC)
    async with osm_sessions() as session:
        await session.execute(
            text("""
INSERT INTO osm_features VALUES
 ('relation', 9, ST_GeomFromText('POLYGON((9.4 54.7,9.6 54.7,9.6 54.9,9.4 54.9,9.4 54.7))',4326),
  '{"boundary":"administrative","name":"Flensburg"}', :imported_at),
 ('relation', 3, ST_GeomFromText('POLYGON((9.3 54.6,9.35 54.6,9.35 54.65,9.3 54.65,9.3 54.6))',4326),
  '{"boundary":"administrative","name":"Outside"}', :imported_at),
 ('node', 2, ST_SetSRID(ST_Point(9.5,54.8),4326), '{"place":"suburb"}', :imported_at)
"""),
            {"imported_at": imported_at},
        )
        await session.commit()
        service = HostOsmSnapshotQueries()
        first = await service.list_features(
            session,
            OsmSnapshotQuery(
                geometry_kinds=("area",),
                tag_filters=(OsmTagFilter("boundary", ("administrative",)),),
                bbox=(9.25, 54.55, 9.7, 55.0),
                limit=1,
            ),
        )
        second = await service.list_features(
            session,
            OsmSnapshotQuery(
                geometry_kinds=("area",),
                tag_filters=(OsmTagFilter("boundary", ("administrative",)),),
                bbox=(9.25, 54.55, 9.7, 55.0),
                cursor=first.next_cursor,
                limit=1,
            ),
        )

    assert [(item.osm_type, item.osm_id) for item in first.items + second.items] == [
        ("relation", 3),
        ("relation", 9),
    ]
    assert first.next_cursor is not None
    assert second.next_cursor is None
    assert second.items[0].tags["name"] == "Flensburg"
    assert second.items[0].geometry_wkb

    async with osm_sessions() as session:
        point_page = await HostOsmSnapshotQueries().list_features(
            session, OsmSnapshotQuery(geometry_kinds=("point",))
        )
    assert point_page.items[0].bbox == (9.5, 54.8, 9.5, 54.8)

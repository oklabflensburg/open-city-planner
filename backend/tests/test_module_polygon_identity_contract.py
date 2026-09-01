import ast
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.integrations.module_host_ports import HostPolygonIdentities
from app.platform.events import InProcessEventBus
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    POLYGON_IDENTITY_MAX_UUIDS,
    POLYGON_IDENTITY_SERVICE_ID,
    POLYGON_IDENTITY_SERVICE_VERSION,
    PolygonIdentity,
    PolygonIdentityPort,
    PolygonIdentityRequest,
    PolygonIdentityResult,
    PolygonSpatialMatch,
    PolygonSpatialMatchRequest,
    PolygonSpatialMatchResult,
)
from app.platform.modules.testing import (
    FakePolygonIdentities,
    FakePolygonSpatialMatches,
    create_test_module_context,
)
from tests.fixtures.polygon_identity_contract_module import (
    DEFINITION,
    PolygonIdentityContractConsumerModule,
)
from tests.test_module_runtime import FakeDiscovery

UUID_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
UUID_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
UUID_MISSING = uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


def test_identity_dtos_are_bounded_immutable_deduplicated_and_orm_free() -> None:
    request = PolygonIdentityRequest((UUID_A, UUID_A, UUID_B))
    identity = PolygonIdentity(7, UUID_A)
    result = PolygonIdentityResult((identity,), (UUID_MISSING,))

    assert request.polygon_uuids == (UUID_A, UUID_B)
    assert result.resolved == (identity,)
    with pytest.raises(AttributeError):
        identity.id = 9  # type: ignore[misc]
    with pytest.raises(TypeError, match="immutable tuple"):
        PolygonIdentityRequest([UUID_A])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="UUID values"):
        PolygonIdentityRequest((str(UUID_A),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at most"):
        PolygonIdentityRequest(tuple(uuid.uuid4() for _ in range(POLYGON_IDENTITY_MAX_UUIDS + 1)))
    with pytest.raises(ValueError, match="disjoint"):
        PolygonIdentityResult((identity,), (UUID_A,))

    rendered_hints = repr(
        {
            cls.__name__: get_type_hints(cls)
            for cls in (
                PolygonIdentity,
                PolygonIdentityRequest,
                PolygonIdentityResult,
            )
        }
    ).lower()
    assert "sqlalchemy" not in rendered_hints
    assert "app.models" not in rendered_hints
    assert "app.db" not in rendered_hints


@pytest.mark.asyncio
async def test_test_context_exposes_semantic_identity_fake() -> None:
    context = create_test_module_context()
    assert context.services is not None
    service = context.services.require(
        PolygonIdentityPort,
        service_id=POLYGON_IDENTITY_SERVICE_ID,
        version=POLYGON_IDENTITY_SERVICE_VERSION,
    )
    assert isinstance(service, FakePolygonIdentities)
    request = PolygonIdentityRequest((UUID_A, UUID_A))

    result = await service.resolve(object(), request)  # type: ignore[arg-type]

    assert service.calls == [request]
    assert result == PolygonIdentityResult((), (UUID_A,))


@pytest.mark.asyncio
async def test_fake_preserves_unique_input_order_and_reports_missing() -> None:
    fake = FakePolygonIdentities((PolygonIdentity(7, UUID_A), PolygonIdentity(11, UUID_B)))

    result = await fake.resolve(
        object(), PolygonIdentityRequest((UUID_B, UUID_A, UUID_B, UUID_MISSING))
    )

    assert result.resolved == (PolygonIdentity(11, UUID_B), PolygonIdentity(7, UUID_A))
    assert result.missing == (UUID_MISSING,)


@pytest.mark.asyncio
async def test_host_adapter_uses_one_read_only_array_query_and_input_order() -> None:
    rows = [SimpleNamespace(id=7, uuid=UUID_A), SimpleNamespace(id=11, uuid=UUID_B)]
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(all=lambda: rows)
    request = PolygonIdentityRequest((UUID_B, UUID_A, UUID_B, UUID_MISSING))

    result = await HostPolygonIdentities().resolve(session, request)

    assert result.resolved == (PolygonIdentity(11, UUID_B), PolygonIdentity(7, UUID_A))
    assert result.missing == (UUID_MISSING,)
    session.execute.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "user_polygons.uuid = ANY" in str(compiled)
    assert len(compiled.params) == 1
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.flush.assert_not_awaited()


def test_identity_adapter_is_consumer_neutral_and_read_only() -> None:
    source_path = Path(__file__).parents[1] / "app/integrations/module_host_ports.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    adapter_source = ast.get_source_segment(
        source,
        next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "HostPolygonIdentities"
        ),
    )
    assert adapter_source is not None
    lowered = adapter_source.lower()
    assert "userpolygon" in lowered
    for forbidden in (
        "analysis-areas",
        "analysis_area",
        "polygon_analysis_areas",
        "commit(",
        "rollback(",
        "flush(",
        "insert(",
        "update(",
        "delete(",
    ):
        assert forbidden not in lowered


def test_external_fixture_imports_only_public_sdk_under_app() -> None:
    source_path = Path(__file__).parent / "fixtures/polygon_identity_contract_module.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    app_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
    }
    assert app_imports == {"app.platform.modules.sdk"}


@pytest.mark.asyncio
async def test_external_fixture_chains_match_uuid_into_identity_resolution() -> None:
    spatial = FakePolygonSpatialMatches(
        PolygonSpatialMatchResult(
            (PolygonSpatialMatch(str(UUID_A), "consumer:area", "district", 0.5),)
        )
    )
    identities = FakePolygonIdentities((PolygonIdentity(7, UUID_A),))
    factory = ModuleContextFactory(
        ModuleHostServices(
            polygon_spatial_matches=spatial,
            polygon_identities=identities,
        ),
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
    assert isinstance(consumer, PolygonIdentityContractConsumerModule)

    result = await consumer.resolve_matches(object(), PolygonSpatialMatchRequest(()))

    assert result == PolygonIdentityResult((PolygonIdentity(7, UUID_A),), ())
    assert identities.calls == [PolygonIdentityRequest((UUID_A,))]


@pytest_asyncio.fixture
async def identity_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = make_url(get_settings().database_url).set(database="postgres")
    schema = f"test_polygon_identity_{uuid.uuid4().hex}"
    admin = create_async_engine(url)
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except (ConnectionError, DBAPIError, OSError, OperationalError) as exc:
        await admin.dispose()
        pytest.skip(f"PostgreSQL is unavailable: {type(exc).__name__}")
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": f"{schema},public"}}
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE user_polygons (id integer PRIMARY KEY, uuid uuid UNIQUE NOT NULL)"
                )
            )
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.mark.asyncio
async def test_real_db_resolution_is_repeatable_for_multiple_consumers_without_mutation(
    identity_sessions,
) -> None:
    async with identity_sessions() as session:
        await session.execute(
            text("INSERT INTO user_polygons (id, uuid) VALUES (7, :uuid_a), (11, :uuid_b)"),
            {"uuid_a": UUID_A, "uuid_b": UUID_B},
        )
        await session.commit()
        before = tuple(
            await session.execute(text("SELECT id, uuid FROM user_polygons ORDER BY id"))
        )
        request = PolygonIdentityRequest((UUID_B, UUID_A, UUID_B, UUID_MISSING))
        resolver = HostPolygonIdentities()

        consumer_a = await resolver.resolve(session, request)
        consumer_b = await resolver.resolve(session, request)
        after = tuple(await session.execute(text("SELECT id, uuid FROM user_polygons ORDER BY id")))

    expected = PolygonIdentityResult(
        (PolygonIdentity(11, UUID_B), PolygonIdentity(7, UUID_A)),
        (UUID_MISSING,),
    )
    assert consumer_a == expected
    assert consumer_b == expected
    assert after == before

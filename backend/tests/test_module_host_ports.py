from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.integrations import module_host_ports
from app.integrations.module_host_ports import (
    HostCacheGenerations,
    HostMapPreviews,
    HostModuleCache,
    HostPolygonAnalytics,
    HostPublicQueries,
)
from app.platform.modules.sdk import (
    MapPreviewRequest,
    MapPreviewUnavailableError,
    PolygonFilterValues,
)
from app.schemas.analytics import BenchmarkMetrics
from app.services.map_previews import MapPreview, MapPreviewError


@pytest.mark.asyncio
async def test_module_cache_namespaces_keys_and_hides_cache_service(monkeypatch) -> None:
    get = AsyncMock(return_value=b"value")
    set_value = AsyncMock(return_value=True)
    clear = AsyncMock(return_value=2)
    monkeypatch.setattr(module_host_ports.cache_service, "get", get)
    monkeypatch.setattr(module_host_ports.cache_service, "set", set_value)
    monkeypatch.setattr(module_host_ports.cache_service, "delete_pattern", clear)
    cache = HostModuleCache("example")

    assert await cache.get("item") == b"value"
    assert await cache.set("item", b"new", ttl_seconds=30)
    assert await cache.clear() == 2

    key = get.await_args.args[0]
    assert key.endswith(":module:example:item")
    assert set_value.await_args.args == (key, b"new", 30)
    assert clear.await_args.args == (key.removesuffix("item") + "*",)


@pytest.mark.asyncio
async def test_cache_generations_delegate_without_exposing_storage(monkeypatch) -> None:
    current = AsyncMock(return_value=7)
    monkeypatch.setattr(module_host_ports, "cache_version", current)
    port = HostCacheGenerations()
    session = object()

    assert await port.current(session, "analytics") == 7
    current.assert_awaited_once_with(session, "analytics")


@pytest.mark.asyncio
async def test_public_query_port_delegates_guard_and_abstracts_timeout(monkeypatch) -> None:
    guard = AsyncMock()
    monkeypatch.setattr(module_host_ports, "guard_public_query", guard)
    monkeypatch.setattr(module_host_ports, "is_statement_timeout_error", lambda error: True)
    settings = SimpleNamespace(public_polygon_response_limit=123, cache_debug_headers=True)
    port = HostPublicQueries(settings)
    request, session = object(), object()

    await port.guard(request, session, "expensive-query")

    guard.assert_awaited_once_with(request, session, "expensive-query")
    assert port.limits.max_response_items == 123
    assert port.limits.cache_debug_headers is True
    assert port.is_timeout(RuntimeError()) is True


@pytest.mark.asyncio
async def test_preview_port_returns_public_result_and_maps_private_error(monkeypatch) -> None:
    request = MapPreviewRequest(
        slug="mitte",
        updated_at=datetime.now(UTC),
        geometry={"type": "Polygon", "coordinates": []},
        bbox=(9.4, 54.7, 9.5, 54.8),
        width=640,
        height=360,
    )
    monkeypatch.setattr(
        module_host_ports.map_preview_service,
        "get",
        AsyncMock(return_value=MapPreview(b"RIFF", '"etag"', True)),
    )

    result = await HostMapPreviews().render(request)

    assert result.body == b"RIFF"
    assert result.content_type == "image/webp"
    assert result.etag == '"etag"'
    assert result.cache_hit is True

    monkeypatch.setattr(
        module_host_ports.map_preview_service,
        "get",
        AsyncMock(side_effect=MapPreviewError("renderer offline")),
    )
    with pytest.raises(MapPreviewUnavailableError, match="renderer offline"):
        await HostMapPreviews().render(request)


@pytest.mark.asyncio
async def test_polygon_analytics_maps_private_schema_to_frozen_sdk_dto(monkeypatch) -> None:
    session = SimpleNamespace(scalar=AsyncMock(return_value=1))
    monkeypatch.setattr(module_host_ports.analytics, "_base_filters", lambda *args: [])
    monkeypatch.setattr(
        module_host_ports.analytics,
        "_benchmark_metrics",
        AsyncMock(
            return_value=BenchmarkMetrics(
                polygon_count=2,
                occupied_count=1,
                vacant_count=1,
                chain_count=0,
                independent_count=1,
                known_occupancy_count=2,
                known_business_structure_count=1,
            )
        ),
    )

    result = await HostPolygonAnalytics().metrics_for_area(
        session, uuid4(), PolygonFilterValues(categories=("food",))
    )

    assert result is not None
    assert result.polygon_count == 2
    assert result.vacancy_rate is None
    assert not hasattr(result, "_sa_instance_state")

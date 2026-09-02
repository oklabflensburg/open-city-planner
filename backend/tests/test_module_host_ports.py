import ast
import inspect
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.integrations import module_host_ports
from app.integrations.module_host_ports import (
    HostCacheGenerations,
    HostMapPreviews,
    HostModuleCache,
    HostPolygonAnalytics,
    HostPolygonQueries,
    HostPublicQueries,
)
from app.platform.modules.sdk import (
    MapPreviewRequest,
    MapPreviewUnavailableError,
    PolygonFilterValues,
    PolygonScope,
)
from app.schemas.polygon_analytics import BenchmarkMetrics
from app.services.map_previews import MapPreview, MapPreviewError

ROOT = Path(__file__).resolve().parents[2]


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
    bump = AsyncMock()
    monkeypatch.setattr(module_host_ports, "cache_version", current)
    monkeypatch.setattr(module_host_ports, "bump_cache_versions", bump)
    port = HostCacheGenerations()
    session = object()

    assert await port.current(session, "analytics") == 7
    await port.bump(session, ("analytics", "polygons", "analytics"))

    current.assert_awaited_once_with(session, "analytics")
    bump.assert_awaited_once_with(
        session, ("analytics", "polygons", "analytics")
    )


def test_cache_generation_adapter_is_generic() -> None:
    source = inspect.getsource(HostCacheGenerations).lower()

    assert "analysis-areas" not in source
    assert "analysis_areas" not in source


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
    session = object()
    monkeypatch.setattr(module_host_ports.polygon_analytics, "base_filters", lambda *args: [])
    monkeypatch.setattr(
        module_host_ports.polygon_analytics,
        "benchmark_metrics",
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

    result = await HostPolygonAnalytics().metrics(
        session, PolygonScope((7, 11)), PolygonFilterValues(categories=("food",))
    )

    assert result is not None
    assert result.polygon_count == 2
    assert result.vacancy_rate is None
    assert not hasattr(result, "_sa_instance_state")


def test_polygon_scope_uses_one_array_parameter_instead_of_expanding_ids() -> None:
    expression = module_host_ports._polygon_scope_filter(PolygonScope((7, 11, 13)))
    compiled = expression.compile(dialect=postgresql.dialect())

    assert "user_polygons.id = ANY" in str(compiled)
    assert len(compiled.params) == 1
    assert tuple(next(iter(compiled.params.values()))) == (7, 11, 13)


@pytest.mark.asyncio
async def test_polygon_query_uses_neutral_scope_and_returns_public_dtos() -> None:
    rows = [
        {
            "uuid": "8ed4671e-7080-4bd8-965c-8f4191bb2bb0",
            "slug": "markt-1",
            "name": "Markt 1",
            "category": "food",
            "floor": "EG",
            "address_display_name": "Markt 1, Flensburg",
            "occupancy_status": "OCCUPIED",
            "area_m2": 42.5,
        }
    ]
    result = SimpleNamespace(mappings=lambda: rows)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    values = await HostPolygonQueries().list_by_scope(
        session, PolygonScope((7,)), limit=25
    )

    assert len(values) == 1
    assert values[0].slug == "markt-1"
    statement = session.execute.await_args.args[0]
    assert "analysis_area" not in str(statement).lower()
    assert " = ANY" in str(statement)


def test_module_port_adapters_do_not_import_analysis_areas() -> None:
    adapter_root = ROOT / "backend/app/integrations"
    sources = sorted(adapter_root.glob("*module*port*.py"))

    assert sources
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(
            name == "app.modules.analysis_areas"
            or name.startswith("app.modules.analysis_areas.")
            for name in imports
        ), f"{source} must not import app.modules.analysis_areas"


def test_slim_host_has_no_statistics_runtime_implementation_or_sql() -> None:
    production = ROOT / "backend/app"
    sources = sorted(production.rglob("*.py"))
    combined = "\n".join(source.read_text(encoding="utf-8") for source in sources)

    assert "HostStatisticsQueries" not in combined
    assert "class SqlStatisticsQueryService" not in combined
    for table in (
        "external_area_mappings",
        "statistical_datasets",
        "statistical_metrics",
        "statistical_observations",
    ):
        assert table not in combined
    assert not (production / "models/statistics.py").exists()


def test_module_host_ports_import_without_builtin_analysis_areas() -> None:
    code = """
import importlib.abc
import sys

class BlockAnalysisAreas(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app.modules.analysis_areas" or fullname.startswith(
            "app.modules.analysis_areas."
        ):
            raise ModuleNotFoundError(fullname)
        return None

sys.meta_path.insert(0, BlockAnalysisAreas())
from app.integrations.module_host_ports import HostPolygonAnalytics, HostPolygonQueries
assert HostPolygonAnalytics and HostPolygonQueries
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT / "backend",
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr

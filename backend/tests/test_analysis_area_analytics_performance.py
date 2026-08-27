import re
import uuid
from collections import Counter
from importlib import import_module
from unittest.mock import AsyncMock

import httpx
import pytest
from shapely.geometry import LineString, Point, Polygon
from sqlalchemy.exc import DBAPIError

analysis_area_api_routes = import_module("app.modules.analysis_areas.api.router")
from app.db.session import get_session
from app.main import app
from app.models.osm_feature import OsmFeature
from app.modules.analysis_areas.application import legacy_queries as analysis_area_api
from app.modules.analysis_areas.application.legacy_queries import (
    AREA_POI_ANALYTICS_SQL,
    _area_poi_categories,
)


class Rows:
    def __init__(self, values: list[tuple[str, int]]) -> None:
        self.values = values

    def all(self) -> list[tuple[str, int]]:
        return self.values


class SpatialFixtureSession:
    def __init__(self) -> None:
        self.area = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        self.features = [
            (Point(2, 2), {"shop": "supermarket"}),
            (Point(3, 3), {"amenity": "cafe"}),
            (Point(4, 4), {"amenity": "cafe"}),
            (Point(20, 20), {"amenity": "cafe"}),
            (LineString([(1, 5), (9, 5)]), {"tourism": "museum"}),
            (Polygon([(6, 6), (8, 6), (8, 8), (6, 8)]), {"leisure": "park"}),
            (Point(5, 5), {"name": "Ohne POI-Kategorie"}),
        ]

    async def execute(self, statement, params):
        assert statement is AREA_POI_ANALYTICS_SQL
        assert params == {"id": 17}
        counts: Counter[str] = Counter()
        for geometry, tags in self.features:
            category = next(
                (tags[key] for key in ("shop", "amenity", "tourism", "leisure") if key in tags),
                None,
            )
            if category is not None and self.area.covers(geometry.representative_point()):
                counts[category] += 1
        return Rows(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def test_area_poi_query_prefilters_with_indexable_geometry_bbox() -> None:
    sql = re.sub(r"\s+", " ", str(AREA_POI_ANALYTICS_SQL)).lower()
    assert "with target as" in sql
    assert "osm.geometry && target.geometry" in sql
    assert "st_covers(target.geometry, st_pointonsurface(osm.geometry))" in sql
    assert sql.index("osm.geometry && target.geometry") < sql.index("st_covers(")
    assert "select geometry from analysis_areas where id = :id" in sql


@pytest.mark.asyncio
async def test_area_poi_spatial_semantics_and_category_grouping() -> None:
    result = await _area_poi_categories(SpatialFixtureSession(), 17)

    assert [(item.category, item.count) for item in result] == [
        ("cafe", 2),
        ("museum", 1),
        ("park", 1),
        ("supermarket", 1),
    ]


def test_partial_poi_geometry_index_matches_query_predicate() -> None:
    index = next(
        item
        for item in OsmFeature.__table__.indexes
        if item.name == "idx_osm_features_poi_geometry"
    )
    assert index.dialect_options["postgresql"]["using"] == "gist"
    predicate = str(index.dialect_options["postgresql"]["where"])
    for key in ("shop", "amenity", "tourism", "leisure"):
        assert f"tags ? '{key}'" in predicate


class QueryCanceledError(Exception):
    sqlstate = "57014"


@pytest.mark.asyncio
async def test_area_analytics_timeout_returns_stable_503_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    area_id = uuid.uuid4()
    database_error = DBAPIError(
        "SELECT vertrauliche_interne_query",
        {},
        QueryCanceledError("canceling statement due to statement timeout"),
        False,
    )

    async def override_session():
        yield session

    monkeypatch.setattr(
        analysis_area_api_routes, "guard_public_query", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        analysis_area_api_routes, "area_uuid_by_slug", AsyncMock(return_value=area_id)
    )
    monkeypatch.setattr(
        analysis_area_api_routes, "area_analytics", AsyncMock(side_effect=database_error)
    )
    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/analysis-areas/by-slug/test/analytics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "error": {
                "code": "ANALYTICS_QUERY_TIMEOUT",
                "message": "Die Gebietsanalyse konnte nicht rechtzeitig abgeschlossen werden.",
            }
        }
    }
    assert "vertrauliche_interne_query" not in response.text
    assert "statement timeout" not in response.text
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_timeout_database_error_is_not_masked() -> None:
    session = AsyncMock()
    database_error = DBAPIError("SELECT 1", {}, RuntimeError("connection lost"), False)

    with pytest.raises(DBAPIError) as exc_info:
        await analysis_area_api_routes._raise_analytics_database_error(session, database_error)

    assert exc_info.value is database_error
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_area_analytics_keeps_versioned_cache_and_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    area_id = uuid.uuid4()
    get_or_compute = AsyncMock(return_value=(None, "HIT"))
    monkeypatch.setattr(analysis_area_api, "cache_version", AsyncMock(return_value=9))
    monkeypatch.setattr(analysis_area_api.cache_service, "get_or_compute", get_or_compute)

    result = await analysis_area_api.area_analytics(
        session,
        area_id,
        categories=(),
        floors=(),
        area_sizes=(),
        occupancy_statuses=(),
        business_structures=(),
        sources=(),
    )

    assert result is None
    call = get_or_compute.await_args
    assert ":analysis-area:analytics:v9:" in call.args[0]
    assert call.kwargs["resource"] == "analysis-area-analytics"
    assert call.kwargs["ttl"] == analysis_area_api.get_settings().analytics_cache_ttl

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.api.osm import router as osm_router
from app.schemas.osm import OsmViewportQuery
from app.services import osm_features
from app.services.osm_features import (
    VIEWPORT_SQL,
    osm_feature_detail,
    selected_categories,
    viewport_features,
)


class MappingRows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "MappingRows":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows

    def first(self) -> dict[str, object] | None:
        return self.rows[0] if self.rows else None


def query(**overrides: object) -> OsmViewportQuery:
    values = {
        "west": 9.43, "south": 54.78, "east": 9.44, "north": 54.79,
        "zoom": 17, "limit": 2,
    }
    values.update(overrides)
    return OsmViewportQuery(**values)


def test_bbox_and_zoom_validation_rejects_invalid_or_excessive_requests() -> None:
    with pytest.raises(ValidationError):
        query(west=9.45, east=9.44)
    with pytest.raises(ValidationError):
        query(south=54.8, north=54.7)
    with pytest.raises(ValidationError):
        query(west=9.0, east=10.0, zoom=17)
    with pytest.raises(ValidationError):
        query(zoom=25)


def test_category_filter_is_allowlisted() -> None:
    assert selected_categories("retail,health,retail") == ("retail", "health")
    with pytest.raises(ValueError):
        selected_categories("retail,drop table")


@pytest.mark.asyncio
async def test_viewport_normalizes_point_polygon_and_multipolygon_and_limits() -> None:
    osm_features._cache.clear()
    imported_at = datetime(2026, 8, 13, tzinfo=UTC)
    rows = [
        {"osm_type": "node", "osm_id": 1, "tags": {"name": "Café"}, "category": "gastronomy", "dimension": 0, "imported_at": imported_at, "geometry": {"type": "Point", "coordinates": [9.435, 54.783]}, "primary_type": "cafe"},
        {"osm_type": "way", "osm_id": 2, "tags": {"name": "Markt"}, "category": "retail", "dimension": 2, "imported_at": imported_at, "geometry": {"type": "Polygon", "coordinates": []}, "primary_type": "supermarket"},
        {"osm_type": "relation", "osm_id": 3, "tags": {"name": "Park"}, "category": "leisure", "dimension": 2, "imported_at": imported_at, "geometry": {"type": "MultiPolygon", "coordinates": []}, "primary_type": "park"},
    ]
    session = AsyncMock()
    session.execute.return_value = MappingRows(rows)

    result = await viewport_features(session, query())

    assert [feature.id for feature in result.features] == ["node/1", "way/2"]
    assert result.features[0].properties.feature_type == "point"
    assert result.features[1].properties.feature_type == "polygon"
    assert result.meta.truncated is True
    assert result.meta.summary == {"gastronomy": 1, "retail": 1}
    assert result.meta.osm_data_updated_at == imported_at


@pytest.mark.asyncio
async def test_low_zoom_returns_empty_without_database_query() -> None:
    session = AsyncMock()
    result = await viewport_features(
        session,
        OsmViewportQuery(west=-180, south=-80, east=180, north=80, zoom=8),
    )
    assert result.features == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_detail_is_on_demand_and_does_not_expose_unknown_tags() -> None:
    session = AsyncMock()
    session.execute.return_value = MappingRows([{
        "osm_type": "way", "osm_id": 42,
        "tags": {"name": "Test", "shop": "books", "private_note": "hidden"},
        "longitude": 9.43, "latitude": 54.78,
    }])
    result = await osm_feature_detail(session, osm_type="way", osm_id=42)
    assert result and result.name == "Test"
    assert "private_note" not in result.tags


def test_viewport_sql_preserves_spatial_index_and_zoom_policy() -> None:
    sql = str(VIEWPORT_SQL)
    assert "ST_MakeEnvelope" in sql
    assert "osm.geometry && bounds.geometry" in sql
    assert "ST_Intersects" in sql
    assert "ST_IsValid" in sql
    assert "ST_SimplifyPreserveTopology" in sql
    assert "category <> 'building'" in sql
    assert ":zoom >= 17 OR category <> 'building'" in sql
    assert "LIMIT" in sql


def test_public_osm_routes_are_registered_without_auth_dependency() -> None:
    paths = {route.path for route in osm_router.routes}
    assert "/osm/features" in paths
    assert "/osm/features/{osm_type}/{osm_id}" in paths

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.analytics import ComparableResult, LocationAnalysis
from app.services.comparables import COMPARABLES_SQL, comparable_polygons
from app.services.location_analytics import POI_COUNTS_SQL, polygon_location_analysis


class MappingRows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "MappingRows":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows

    def first(self) -> dict[str, object] | None:
        return self.rows[0] if self.rows else None


@pytest.mark.asyncio
async def test_poi_radius_uses_real_postgis_distance_and_local_osm_data() -> None:
    imported_at = datetime(2026, 8, 14, tzinfo=UTC)
    session = AsyncMock()
    session.scalar.return_value = True
    session.execute.side_effect = [
        MappingRows([
            {"category": "gastronomy", "count": 7, "reference_date": imported_at},
            {"category": "public_transport", "count": 2, "reference_date": imported_at},
        ]),
        MappingRows([{"category": "public_transport", "name": "ZOB", "distance_m": 123.4}]),
    ]

    result = await polygon_location_analysis(session, slug="test", radius_m=500)

    assert isinstance(result, LocationAnalysis)
    assert [(item.label, item.count) for item in result.poi_counts] == [("Gastronomie", 7), ("ÖPNV", 2)]
    assert result.nearest_public_transport and result.nearest_public_transport.name == "ZOB"
    assert result.reference_date == imported_at
    sql = str(POI_COUNTS_SQL)
    assert "ST_DWithin" in sql
    assert "::geography" in sql
    assert "osm.geometry &&" in sql


@pytest.mark.asyncio
async def test_missing_polygon_has_no_location_fallback() -> None:
    session = AsyncMock()
    session.scalar.return_value = False
    assert await polygon_location_analysis(session, slug="missing", radius_m=500) is None
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_comparables_are_transparent_and_public_dto_has_no_internal_fields() -> None:
    session = AsyncMock()
    session.scalar.return_value = True
    session.execute.return_value = MappingRows([{
        "slug": "vergleich", "name": "Vergleichsfläche", "distance_m": 210.0,
        "area_m2": 124.0, "category": "fashion", "floor": "EG", "similarity_score": 0.87,
    }])

    result = await comparable_polygons(session, slug="ziel")

    assert isinstance(result, ComparableResult)
    assert result.items[0].similarity_score == 0.87
    payload = result.model_dump()
    assert "price_per_sqm" not in str(payload)
    assert "owner_name" not in str(payload)
    sql = str(COMPARABLES_SQL)
    assert "ST_Distance" in sql
    assert "category" in sql and "floor" in sql and "area_m2" in sql

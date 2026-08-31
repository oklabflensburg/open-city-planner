import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.city_metrics import CityMetrics
from app.schemas.analytics import AreaCompareFilters, AreaCompareRequest
from app.services import analytics as analytics_service
from app.services.analytics import (
    AreaAnalyticsScope,
    _compare_areas_uncached,
    _compare_metrics_by_area,
    analytics_overview,
    market_benchmarks,
)


class Rows:
    def __init__(self, values: list[tuple[str, int]]) -> None:
        self.values = values

    def all(self) -> list[tuple[str, int]]:
        return self.values


class MappingRows:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values = values or {
            "polygon_count": 0,
            "total_area_m2": None,
            "average_area_m2": None,
            "known_occupancy_count": 0,
            "vacant_count": 0,
            "known_business_count": 0,
            "chain_count": 0,
        }

    def mappings(self) -> "MappingRows":
        return self

    def one(self) -> dict[str, object]:
        return self.values


class CompareRows:
    def __init__(self, values: list[dict[str, object]]) -> None:
        self.values = values

    def mappings(self) -> "CompareRows":
        return self

    def all(self) -> list[dict[str, object]]:
        return self.values

    def one_or_none(self) -> dict[str, object] | None:
        return self.values[0] if self.values else None


@pytest.mark.asyncio
async def test_analytics_uses_database_counts_and_keeps_unavailable_metrics_null() -> None:
    session = AsyncMock()
    session.execute.side_effect = [
        Rows([("fashion", 4), ("food", 2), ("otherAreas", 3)]),
        Rows([("fashion", 4), ("otherAreas", 3)]),
        MappingRows({
            "polygon_count": 7, "total_area_m2": 700.0, "average_area_m2": 100.0,
            "known_occupancy_count": 5, "vacant_count": 1,
            "known_business_count": 4, "chain_count": 2,
        }),
    ]
    session.scalar.return_value = None

    result = await analytics_overview(
        session,
        categories=("fashion", "otherAreas"),
        floors=("EG",),
        area_sizes=("M",),
    )

    assert result.fast_facts.shops == 4
    assert result.fast_facts.vacancy_rate is None
    assert result.fast_facts.chain_store_rate is None
    assert result.fast_facts.centrality_index is None
    assert result.fast_facts.purchasing_power_index is None
    assert result.fast_facts.total_area_m2 == 700.0
    assert result.fast_facts.calculated_vacancy_rate == 20.0
    assert result.fast_facts.calculated_chain_store_rate == 50.0
    assert [(item.category, item.count) for item in result.category_counts] == [
        ("fashion", 4),
        ("food", 2),
        ("otherAreas", 3),
    ]
    assert result.prime_rents.rows == []
    statements = [str(call.args[0]) for call in session.execute.await_args_list]
    assert "user_polygons.floor" in statements[0]
    assert "user_polygons.category" in statements[1]


@pytest.mark.asyncio
async def test_empty_database_returns_zero_shops_and_no_mock_values() -> None:
    session = AsyncMock()
    session.execute.side_effect = [Rows([]), Rows([]), MappingRows()]
    session.scalar.return_value = None

    result = await analytics_overview(session)

    assert result.fast_facts.shops == 0
    assert result.fast_facts.updated_at is None
    assert result.industry_distribution == []
    assert result.category_counts == []


@pytest.mark.asyncio
async def test_overview_reads_persisted_city_metrics() -> None:
    session = AsyncMock()
    session.execute.side_effect = [Rows([]), Rows([]), MappingRows()]
    session.scalar.return_value = CityMetrics(
        id=uuid.uuid4(),
        vacancy_rate=Decimal("6.25"),
        chain_store_rate=Decimal("71.00"),
        centrality_index=Decimal("154.00"),
        purchasing_power_index=Decimal("85.00"),
        reference_date=date(2026, 6, 30),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    result = await analytics_overview(session)

    assert result.fast_facts.vacancy_rate == Decimal("6.25")
    assert result.fast_facts.chain_store_rate == Decimal("71.00")
    assert result.fast_facts.centrality_index == Decimal("154.00")
    assert result.fast_facts.purchasing_power_index == Decimal("85.00")
    assert result.fast_facts.reference_date == date(2026, 6, 30)


@pytest.mark.asyncio
async def test_benchmarks_compare_filtered_selection_with_city_without_mock_values() -> None:
    session = AsyncMock()
    session.execute.side_effect = [
        MappingRows({
            "polygon_count": 4, "total_area_m2": 800.0, "average_area_m2": 200.0,
            "known_occupancy_count": 4, "vacant_count": 1,
            "known_business_count": 2, "chain_count": 1,
        }),
        MappingRows({
            "polygon_count": 10, "total_area_m2": 2500.0, "average_area_m2": 250.0,
            "known_occupancy_count": 8, "vacant_count": 2,
            "known_business_count": 5, "chain_count": 2,
        }),
    ]

    result = await market_benchmarks(
        session,
        categories=("fashion",),
        occupancy_statuses=("VACANT",),
    )

    assert [item.label for item in result.items] == ["Aktuelle Auswahl", "Gesamtstadt"]
    assert result.items[0].metrics.vacancy_rate == 25.0
    assert result.items[0].metrics.chain_store_rate == 50.0
    assert result.items[1].metrics.polygon_count == 10
    statements = [str(call.args[0]) for call in session.execute.await_args_list]
    assert "occupancy_status" in statements[0]
    assert "price_per_sqm" not in statements[0]


@pytest.mark.asyncio
async def test_compare_groups_distinct_area_metrics_in_one_query() -> None:
    session = AsyncMock()
    common = {
        "total_area_m2": None, "average_area_m2": None, "median_area_m2": None,
        "occupied_count": 0, "chain_count": 0, "independent_count": 0,
        "known_business_count": 0, "data_updated_at": None,
    }
    session.execute.return_value = CompareRows([
        {**common, "analysis_area_id": 11, "polygon_count": 10, "vacant_count": 2, "known_occupancy_count": 10},
        {**common, "analysis_area_id": 12, "polygon_count": 5, "vacant_count": 1, "known_occupancy_count": 4},
        {**common, "analysis_area_id": 13, "polygon_count": 20, "vacant_count": 3, "known_occupancy_count": 15},
    ])

    result = await _compare_metrics_by_area(
        session, [11, 12, 13], AreaCompareFilters(categories=["gastronomy"])
    )

    assert result[11].polygon_count == 10
    assert result[12].polygon_count == 5
    assert result[13].polygon_count == 20
    assert result[11].vacancy_rate == 20.0
    assert result[12].vacancy_rate == 25.0
    statement = str(session.execute.await_args.args[0])
    assert "GROUP BY polygon_analysis_areas.analysis_area_id" in statement
    assert "user_polygons.category" in statement


@pytest.mark.asyncio
async def test_compare_benchmark_resolves_covering_municipality_not_selected_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    district = AreaAnalyticsScope(
        id=11, uuid=uuid.uuid4(), slug="innenstadt", name="Innenstadt",
        area_type="DISTRICT", parent_id=20, geometry="district-geometry",
        centroid="district-centroid", area_m2=1_000_000,
    )
    municipality = AreaAnalyticsScope(
        id=20, uuid=uuid.uuid4(), slug="flensburg", name="Flensburg",
        area_type="MUNICIPALITY", parent_id=None, geometry="city-geometry",
        centroid="city-centroid", area_m2=56_000_000,
    )
    session = AsyncMock()
    session.execute.side_effect = [
        CompareRows([{
            "id": district.id, "uuid": district.uuid, "slug": district.slug,
            "name": district.name, "area_type": district.area_type,
            "parent_id": district.parent_id, "area_m2": district.area_m2,
            "geometry": district.geometry, "centroid": district.centroid,
            "parent_name": "Flensburg",
        }]),
        CompareRows([{
            "id": municipality.id, "uuid": municipality.uuid,
            "slug": municipality.slug, "name": municipality.name,
            "area_type": municipality.area_type, "parent_id": municipality.parent_id,
            "area_m2": municipality.area_m2, "geometry": municipality.geometry,
            "centroid": municipality.centroid,
        }]),
    ]
    metrics = AsyncMock(return_value={})
    monkeypatch.setattr(analytics_service, "_compare_metrics_by_area", metrics)

    result = await _compare_areas_uncached(
        session, AreaCompareRequest(area_slugs=["innenstadt"])
    )

    assert [item.slug for item in result.areas] == ["innenstadt"]
    assert result.benchmark is not None
    assert result.benchmark.slug == "flensburg"
    statement = str(session.execute.await_args_list[1].args[0])
    assert "ST_Covers" in statement
    metrics.assert_awaited_once()
    assert metrics.await_args.args[1] == [11, 20]

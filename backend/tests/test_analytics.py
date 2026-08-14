import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.city_metrics import CityMetrics
from app.services.analytics import analytics_overview, market_benchmarks


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

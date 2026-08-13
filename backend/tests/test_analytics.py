import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.models.city_metrics import CityMetrics
from app.services.analytics import analytics_overview


class Rows:
    def __init__(self, values: list[tuple[str, int]]) -> None:
        self.values = values

    def all(self) -> list[tuple[str, int]]:
        return self.values


@pytest.mark.asyncio
async def test_analytics_uses_database_counts_and_keeps_unavailable_metrics_null() -> None:
    session = AsyncMock()
    session.execute.side_effect = [
        Rows([("fashion", 4), ("food", 2), ("otherAreas", 3)]),
        Rows([("fashion", 4), ("otherAreas", 3)]),
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
    session.execute.side_effect = [Rows([]), Rows([])]
    session.scalar.return_value = None

    result = await analytics_overview(session)

    assert result.fast_facts.shops == 0
    assert result.fast_facts.updated_at is None
    assert result.industry_distribution == []
    assert result.category_counts == []


@pytest.mark.asyncio
async def test_overview_reads_persisted_city_metrics() -> None:
    session = AsyncMock()
    session.execute.side_effect = [Rows([]), Rows([])]
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

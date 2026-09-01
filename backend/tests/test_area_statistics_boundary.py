from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.platform.modules.sdk import StatisticsArea, StatisticsSelection
from app.services.area_statistics import (
    _area_statistic_series_uncached,
    _area_statistics_uncached,
)


class MappingResult:
    def __init__(self, *, first=None, rows=()) -> None:
        self._first = first
        self._rows = list(rows)

    def mappings(self):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._rows


def area(identifier: str, slug: str, name: str, level: str) -> StatisticsArea:
    return StatisticsArea(
        id=UUID(identifier), slug=slug, name=name, area_type=level
    )


MUNICIPALITY = area(
    "11111111-1111-4111-8111-111111111111",
    "flensburg",
    "Flensburg",
    "MUNICIPALITY",
)
DISTRICT = area(
    "22222222-2222-4222-8222-222222222222",
    "altstadt-15630273",
    "Altstadt",
    "DISTRICT",
)
QUARTER = area(
    "33333333-3333-4333-8333-333333333333",
    "nordertor-15651154",
    "Nordertor",
    "QUARTER",
)
SOURCE = {
    "last_import_at": datetime(2026, 1, 2, tzinfo=UTC),
    "source_updated_at": datetime(2026, 1, 1, tzinfo=UTC),
}


@pytest.mark.asyncio
async def test_district_statistics_use_neutral_mapping_and_municipality_comparison() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first={"statistics_id": 7, "municipality_id": 1}),
                MappingResult(
                    rows=[
                        {
                            "key": "population",
                            "name": "Bevölkerung",
                            "category": "Bevölkerung",
                            "unit": "persons",
                            "value_numeric": Decimal(3657),
                            "period_start": date(2025, 1, 1),
                            "is_calculated": False,
                            "municipality_value": Decimal(98040),
                        }
                    ]
                ),
                MappingResult(first=SOURCE),
            ]
        )
    )

    result = await _area_statistics_uncached(
        session,
        StatisticsSelection(
            requested=DISTRICT,
            target=DISTRICT,
            municipality=MUNICIPALITY,
        ),
    )

    assert result is not None
    assert result.area.slug == DISTRICT.slug
    assert result.statistics_area.slug == DISTRICT.slug
    assert result.inherited_from_parent is False
    assert result.latest[0].municipality_value == Decimal(98040)
    assert result.latest[0].difference == Decimal(-94383)
    assert "analysis_areas" not in " ".join(
        str(call.args[0]).lower() for call in session.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_quarter_response_preserves_requested_area_and_inherited_target() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first={"statistics_id": 7, "municipality_id": 1}),
                MappingResult(rows=[]),
                MappingResult(first=SOURCE),
            ]
        )
    )

    result = await _area_statistics_uncached(
        session,
        StatisticsSelection(
            requested=QUARTER,
            target=DISTRICT,
            municipality=MUNICIPALITY,
            inherited=True,
        ),
    )

    assert result is not None
    assert result.area.slug == QUARTER.slug
    assert result.statistics_area.slug == DISTRICT.slug
    assert result.inherited_from_parent is True


@pytest.mark.asyncio
async def test_series_uses_the_selected_statistics_mapping() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                MappingResult(first={"statistics_id": 7, "municipality_id": 1}),
                MappingResult(
                    first={
                        "id": 9,
                        "key": "population",
                        "name": "Bevölkerung",
                        "unit": "persons",
                        "category": "Bevölkerung",
                    }
                ),
                MappingResult(
                    rows=[
                        {
                            "period_start": date(2025, 1, 1),
                            "value_numeric": Decimal(3657),
                            "value_text": None,
                        }
                    ]
                ),
                MappingResult(first=SOURCE),
            ]
        )
    )

    result = await _area_statistic_series_uncached(
        session,
        StatisticsSelection(
            requested=DISTRICT,
            target=DISTRICT,
            municipality=MUNICIPALITY,
        ),
        "population",
    )

    assert result is not None
    assert result.series[0].value == Decimal(3657)
    assert "statistical_area_id" in str(session.execute.await_args_list[2].args[0])


@pytest.mark.asyncio
async def test_missing_statistics_mapping_returns_none() -> None:
    session = SimpleNamespace(execute=AsyncMock(return_value=MappingResult(first=None)))

    result = await _area_statistics_uncached(
        session,
        StatisticsSelection(
            requested=MUNICIPALITY,
            target=MUNICIPALITY,
            municipality=MUNICIPALITY,
        ),
    )

    assert result is None

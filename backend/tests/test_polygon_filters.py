import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.schemas.polygon_filters import PolygonFilterParams, polygon_filter_query
from app.services.polygon_filters import floor_group_expression, polygon_filter_clauses


def sql(expression: object) -> str:
    return str(expression.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))


def test_query_accepts_csv_repeated_values_and_removes_duplicates() -> None:
    filters = polygon_filter_query(
        area_sizes=["S,M", "S"], floors=["EG", "OG"],
        categories=["fashion,gastronomy"], occupancy_statuses=["VACANT"],
        business_structures=None, sources=["OSM,STADTPLANNER", "OSM"],
    )

    assert filters.area_sizes == ("S", "M")
    assert filters.floors == ("EG", "OG")
    assert filters.categories == ("fashion", "gastronomy")
    assert filters.occupancy_statuses == ("VACANT",)
    assert filters.sources == ("OSM", "STADTPLANNER")


def test_invalid_enum_value_returns_structured_422() -> None:
    with pytest.raises(HTTPException) as exc_info:
        polygon_filter_query(area_sizes=["XXL"])

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "INVALID_POLYGON_FILTER"


def test_none_source_cannot_be_combined_with_a_real_source() -> None:
    with pytest.raises(HTTPException) as exc_info:
        polygon_filter_query(sources=["NONE,OSM"])

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["code"] == "INVALID_POLYGON_FILTER"


def test_empty_dimensions_add_no_sql_clauses() -> None:
    assert polygon_filter_clauses(PolygonFilterParams()) == []


def test_stadtplanner_source_exclusion_short_circuits_polygon_query() -> None:
    clauses = polygon_filter_clauses(PolygonFilterParams(sources=("OSM",)))
    assert len(clauses) == 1
    assert sql(clauses[0]) == "false"


def test_explicit_no_sources_short_circuits_polygon_query() -> None:
    clauses = polygon_filter_clauses(PolygonFilterParams(sources=("NONE",)))
    assert len(clauses) == 1
    assert sql(clauses[0]) == "false"


def test_dimensions_are_independent_in_clauses_and_values_are_or_combined() -> None:
    clauses = polygon_filter_clauses(PolygonFilterParams(
        area_sizes=("S", "M"), floors=("EG", "OG"),
        categories=("fashion", "gastronomy"), occupancy_statuses=("VACANT",),
    ))

    assert len(clauses) == 4
    rendered = " AND ".join(sql(clause) for clause in clauses)
    assert "IN ('S', 'M')" in rendered
    assert "IN ('EG', 'OG')" in rendered
    assert "IN ('fashion', 'gastronomy')" in rendered
    assert "IN ('VACANT')" in rendered


def test_floor_group_maps_persisted_upper_floors_without_treating_null_as_eg() -> None:
    rendered = sql(floor_group_expression())

    for value in ("OG", "1OG", "2OG", "3OG", "DG"):
        assert value in rendered
    assert "ELSE 'EG'" not in rendered

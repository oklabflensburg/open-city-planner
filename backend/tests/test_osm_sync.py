from datetime import UTC, datetime
from inspect import signature

from app.cli.postprocess_osm import DELETE_SQL, REGION_SQL, UPSERT_SQL, parse_timestamp
from app.services.analysis_areas import sync_osm_analysis_areas


def test_osm_sync_uses_exact_schleswig_holstein_boundary_and_deletes() -> None:
    assert "ISO3166-2'='DE-SH" in REGION_SQL
    assert "ST_Intersects(stage.geometry, region.geometry)" in str(UPSERT_SQL)
    assert "DELETE FROM osm_features" in str(DELETE_SQL)
    assert "NOT EXISTS" in str(DELETE_SQL)


def test_osm_sync_timestamp_is_timezone_aware() -> None:
    assert parse_timestamp("2026-08-18T12:34:56Z") == datetime(
        2026, 8, 18, 12, 34, 56, tzinfo=UTC
    )
    assert parse_timestamp("2026-08-18T12:34:56").tzinfo is UTC


def test_analysis_area_sync_can_join_a_larger_transaction() -> None:
    parameter = signature(sync_osm_analysis_areas).parameters["commit"]
    assert parameter.default is True

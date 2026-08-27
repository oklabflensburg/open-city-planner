from datetime import UTC, datetime
from inspect import signature

from app.cli.postprocess_osm import (
    DELETE_SQL,
    REFRESH_POLYGON_OSM_SOURCES_SQL,
    REGION_SQL,
    UPSERT_SQL,
    parse_timestamp,
)
from app.modules.analysis_areas.application.legacy_sync import sync_osm_analysis_areas


def test_osm_sync_uses_exact_schleswig_holstein_boundary_and_deletes() -> None:
    assert "ISO3166-2'='DE-SH" in REGION_SQL
    assert "ST_Intersects(stage.geometry, region.geometry)" in str(UPSERT_SQL)
    assert "DELETE FROM osm_features" in str(DELETE_SQL)
    assert "NOT EXISTS" in str(DELETE_SQL)


def test_osm_delete_uses_correlated_stage_key_lookup() -> None:
    query = str(DELETE_SQL)
    assert "stage.osm_type = CASE feature.osm_type" in query
    assert "stage.osm_id = feature.osm_id" in query
    assert "stage.geometry && region.geometry" in query
    assert "OFFSET 0" in query
    assert "), selected AS (" not in query


def test_osm_sync_timestamp_is_timezone_aware() -> None:
    assert parse_timestamp("2026-08-18T12:34:56Z") == datetime(
        2026, 8, 18, 12, 34, 56, tzinfo=UTC
    )
    assert parse_timestamp("2026-08-18T12:34:56").tzinfo is UTC


def test_analysis_area_sync_can_join_a_larger_transaction() -> None:
    parameter = signature(sync_osm_analysis_areas).parameters["commit"]
    assert parameter.default is True


def test_hourly_sync_refreshes_adopted_polygon_osm_tags() -> None:
    query = str(REFRESH_POLYGON_OSM_SOURCES_SQL)
    assert "osm_snapshot=feature.tags" in query
    assert "source.osm_type=feature.osm_type" in query

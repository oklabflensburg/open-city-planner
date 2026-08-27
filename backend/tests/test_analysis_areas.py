from app.modules.analysis_areas.application.legacy_sync import (
    CANDIDATES_SQL,
    PARENT_SQL,
    UPSERT_SQL,
)
from app.modules.analysis_areas.persistence.models import AnalysisArea, PolygonAnalysisArea


def test_analysis_area_model_enforces_hierarchy_and_spatial_index() -> None:
    constraints = {constraint.name for constraint in AnalysisArea.__table__.constraints}
    indexes = {index.name: index for index in AnalysisArea.__table__.indexes}
    assert "ck_analysis_areas_type" in constraints
    assert "uq_analysis_areas_source_osm" in constraints
    assert AnalysisArea.__table__.c.slug.unique is True
    assert indexes["idx_analysis_areas_geometry"].dialect_options["postgresql"]["using"] == "gist"
    assert next(iter(AnalysisArea.__table__.c.parent_id.foreign_keys)).ondelete == "SET NULL"


def test_polygon_area_assignment_is_unique_and_cascades() -> None:
    constraints = {constraint.name for constraint in PolygonAnalysisArea.__table__.constraints}
    assert "uq_polygon_analysis_area" in constraints
    assert {foreign_key.ondelete for foreign_key in PolygonAnalysisArea.__table__.foreign_keys} == {"CASCADE"}


def test_osm_area_import_accepts_only_real_polygons_and_spatial_parents() -> None:
    candidates = str(CANDIDATES_SQL)
    parents = str(PARENT_SQL)
    assert "ST_Dimension(feature.geometry)=2" in candidates
    assert "ST_Multi(ST_CollectionExtract(ST_MakeValid" in candidates
    assert "ST_Buffer" not in candidates
    assert "ST_Covers(candidate.geometry, child.centroid)" in parents
    assert "ST_Intersection" in parents


def test_osm_area_import_persists_external_source_tags_and_protects_manual_match() -> None:
    upsert = str(UPSERT_SQL)
    assert "source_osm_wikidata" in upsert
    assert "source_osm_wikipedia" in upsert
    assert "wikidata_match_source='MANUAL'" in upsert
    assert "THEN 'CONFLICT'" in upsert

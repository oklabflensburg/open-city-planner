"""Production contracts captured before the Analysis Areas module migration."""

from app.main import app

EXPECTED_PATHS = {
    "/api/v1/analysis-areas",
    "/api/v1/analysis-areas/geojson",
    "/api/v1/analysis-areas/sitemap",
    "/api/v1/analysis-areas/by-slug/{slug}",
    "/api/v1/analysis-areas/by-slug/{slug}/preview.webp",
    "/api/v1/analysis-areas/by-slug/{slug}/polygons",
    "/api/v1/analysis-areas/by-slug/{slug}/statistics",
    "/api/v1/analysis-areas/by-slug/{slug}/statistics/{metric_key}",
    "/api/v1/analysis-areas/by-slug/{slug}/analytics",
    "/api/v1/analysis-areas/by-slug/{slug}/comparison",
    "/api/v1/analysis-areas/{area_id}",
    "/api/v1/analysis-areas/{area_id}/analytics",
    "/api/v1/analysis-areas/{area_id}/comparison",
}


def test_public_analysis_area_route_inventory_is_stable() -> None:
    paths = set(app.openapi()["paths"])
    assert EXPECTED_PATHS <= paths
    assert not any(path.startswith("/api/v1/modules/analysis-areas") for path in paths)


def test_geojson_and_preview_cache_contract_is_documented_by_routes() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/analysis-areas/geojson"]
    assert "get" in paths["/api/v1/analysis-areas/by-slug/{slug}/preview.webp"]

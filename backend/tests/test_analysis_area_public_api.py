from datetime import UTC, datetime

from app.main import app
from app.modules.analysis_areas.api.schemas import AnalysisAreaDetail, AnalysisAreaPolygon


def test_openapi_documents_public_area_routes_and_unique_operations() -> None:
    schema = app.openapi()
    assert schema["info"]["title"] == "Stadtplaner API"
    assert schema["info"]["version"] == "0.2.0"
    paths = schema["paths"]
    for path in (
        "/api/v1/analysis-areas/by-slug/{slug}",
        "/api/v1/analysis-areas/by-slug/{slug}/analytics",
        "/api/v1/analysis-areas/by-slug/{slug}/comparison",
        "/api/v1/analysis-areas/by-slug/{slug}/polygons",
        "/api/v1/analysis-areas/sitemap",
    ):
        assert path in paths
        assert paths[path]["get"]["summary"]
        assert "Analysis Areas" in paths[path]["get"]["tags"]
    operation_ids = [operation["operationId"] for methods in paths.values() for operation in methods.values() if isinstance(operation, dict) and "operationId" in operation]
    assert len(operation_ids) == len(set(operation_ids))
    assert "AnalysisAreaDetail" in schema["components"]["schemas"]
    cookie_security = schema["components"]["securitySchemes"]["AccessCookie"]
    assert cookie_security == {
        "type": "apiKey", "description": cookie_security["description"],
        "in": "cookie", "name": "ocm_access_token",
    }
    assert paths["/api/v1/polygons"]["post"]["security"] == [{"AccessCookie": []}]


def test_public_polygon_and_geojson_routes_expose_a_cap_limit() -> None:
    schema = app.openapi()
    for path in (
        "/api/v1/polygons",
        "/api/v1/polygons/overview",
        "/api/v1/polygons/geojson",
        "/api/v1/analysis-areas/geojson",
    ):
        params = schema["paths"][path]["get"]["parameters"]
        assert any(parameter["name"] == "limit" for parameter in params)


def test_public_area_dtos_exclude_confidential_management_fields() -> None:
    now = datetime.now(UTC)
    detail = AnalysisAreaDetail(
        id="area-id", slug="innenstadt-123", name="Innenstadt", area_type="DISTRICT",
        area_m2=1_000_000, source="OSM", updated_at=now,
        geometry={"type": "MultiPolygon", "coordinates": [[[(9.4, 54.7), (9.5, 54.7), (9.5, 54.8), (9.4, 54.7)]]]},
        centroid=(9.43, 54.78), bbox=(9.4, 54.7, 9.5, 54.8),
    ).model_dump()
    polygon = AnalysisAreaPolygon(
        id="polygon-id", slug="laden", name="Laden", category="food",
        occupancy_status="OCCUPIED", area_m2=120,
    ).model_dump()
    forbidden = {"owner", "owner_address", "price", "rent", "internal_notes", "notes"}
    assert forbidden.isdisjoint(detail)
    assert forbidden.isdisjoint(polygon)

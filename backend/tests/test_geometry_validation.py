import pytest
from pydantic import ValidationError

from app.schemas.geojson import PolygonGeometry
from app.services.geometry import validate_polygon_geometry


def test_accepts_valid_polygon() -> None:
    geometry = PolygonGeometry(
        type="Polygon",
        coordinates=[[(9.43, 54.78), (9.44, 54.78), (9.44, 54.79), (9.43, 54.78)]],
    )

    polygon = validate_polygon_geometry(geometry)

    assert polygon.geom_type == "Polygon"
    assert polygon.is_valid


def test_rejects_open_ring() -> None:
    with pytest.raises(ValidationError):
        PolygonGeometry(
            type="Polygon",
            coordinates=[[(9.43, 54.78), (9.44, 54.78), (9.44, 54.79), (9.43, 54.79)]],
        )


def test_repairs_self_intersection_to_supported_multipolygon() -> None:
    geometry = PolygonGeometry(
        type="Polygon",
        coordinates=[
            [(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)],
        ],
    )

    repaired = validate_polygon_geometry(geometry)
    assert repaired.geom_type == "MultiPolygon"

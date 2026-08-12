import pytest
from pydantic import ValidationError

from app.schemas.geojson import PolygonCreate, PolygonGeometry


def test_polygon_create_schema() -> None:
    payload = PolygonCreate(
        name="Meine Fläche",
        category="custom",
        geometry=PolygonGeometry(
            type="Polygon",
            coordinates=[[(9.43, 54.78), (9.44, 54.78), (9.44, 54.79), (9.43, 54.78)]],
        ),
    )

    assert payload.properties == {}


def test_rejects_too_few_vertices() -> None:
    with pytest.raises(ValidationError):
        PolygonGeometry(type="Polygon", coordinates=[[(9.43, 54.78), (9.44, 54.78), (9.43, 54.78)]])


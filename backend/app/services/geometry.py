from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely import make_valid
from shapely.geometry import Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry

from app.schemas.geojson import PolygonGeometry


class GeometryValidationError(ValueError):
    pass


def validate_polygon_geometry(geometry: PolygonGeometry) -> Polygon:
    geom = shape(geometry.model_dump())
    if geom.geom_type != "Polygon":
        raise GeometryValidationError("Only Polygon geometries are supported")
    if geom.is_empty:
        raise GeometryValidationError("Polygon must not be empty")
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom.geom_type != "Polygon":
        raise GeometryValidationError("Invalid polygon cannot be repaired to a single polygon")
    return geom


def to_wkb_element(geometry: PolygonGeometry) -> Any:
    polygon = validate_polygon_geometry(geometry)
    return from_shape(polygon, srid=4326)


def from_wkb_element(element: Any) -> dict[str, Any]:
    geom: BaseGeometry = to_shape(element)
    return mapping(geom)


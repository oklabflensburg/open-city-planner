from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry

from app.schemas.geojson import AreaGeometry


class GeometryValidationError(ValueError):
    pass


def validate_polygon_geometry(geometry: AreaGeometry) -> Polygon | MultiPolygon:
    geom = shape(geometry.model_dump())
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise GeometryValidationError("Only Polygon and MultiPolygon geometries are supported")
    if geom.is_empty:
        raise GeometryValidationError("Polygon must not be empty")
    if not geom.is_valid:
        geom = make_valid(geom)
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise GeometryValidationError("Invalid area geometry cannot be repaired")
    return geom


def to_wkb_element(geometry: AreaGeometry) -> Any:
    polygon = validate_polygon_geometry(geometry)
    return from_shape(polygon, srid=4326)


def from_wkb_element(element: Any) -> dict[str, Any]:
    geom: BaseGeometry = to_shape(element)
    return mapping(geom)

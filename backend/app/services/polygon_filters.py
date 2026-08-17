from collections.abc import Collection

from sqlalchemy import case, false

from app.models.user_polygon import UserPolygon
from app.schemas.polygon_filters import PolygonFilterParams

UPPER_FLOORS = ("OG", "1OG", "2OG", "3OG", "DG")


def floor_group_expression():
    """Map the persisted floor values to the three public GIS filter groups."""
    return case(
        (UserPolygon.floor == "UG", "UG"),
        (UserPolygon.floor == "EG", "EG"),
        (UserPolygon.floor.in_(UPPER_FLOORS), "OG"),
        else_=None,
    )


def polygon_filter_clauses(
    filters: PolygonFilterParams,
    *,
    exclude: Collection[str] = (),
) -> list[object]:
    """OR within dimensions, AND between dimensions; empty dimensions are unrestricted."""
    clauses: list[object] = []
    if filters.sources and "STADTPLANNER" not in filters.sources:
        return [false()]
    if filters.categories and "categories" not in exclude:
        clauses.append(UserPolygon.category.in_(filters.categories))
    if filters.floors and "floors" not in exclude:
        clauses.append(floor_group_expression().in_(filters.floors))
    if filters.area_sizes and "area_sizes" not in exclude:
        clauses.append(UserPolygon.properties["size"].as_string().in_(filters.area_sizes))
    if filters.occupancy_statuses and "occupancy_statuses" not in exclude:
        clauses.append(UserPolygon.occupancy_status.in_(filters.occupancy_statuses))
    if filters.business_structures and "business_structures" not in exclude:
        clauses.append(UserPolygon.business_structure.in_(filters.business_structures))
    return clauses

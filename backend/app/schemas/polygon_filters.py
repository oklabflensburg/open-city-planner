from dataclasses import dataclass
from typing import Annotated

from fastapi import HTTPException, Query

CATEGORIES = frozenset({
    "warehouse", "fashion", "food", "electronics", "furniture", "garden",
    "other", "gastronomy", "services", "otherAreas", "__none__",
})
FLOORS = frozenset({"UG", "EG", "OG"})
AREA_SIZES = frozenset({"S", "M", "L", "XL"})
OCCUPANCY_STATUSES = frozenset({"OCCUPIED", "VACANT", "UNKNOWN"})
BUSINESS_STRUCTURES = frozenset({"CHAIN", "INDEPENDENT", "UNKNOWN"})
DATA_SOURCES = frozenset({"STADTPLANNER", "OSM"})
NONE = "NONE"


def _values(raw: list[str] | None, allowed: frozenset[str], field: str) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(
        part.strip()
        for item in (raw or [])
        for part in item.split(",")
        if part.strip()
    ))
    if invalid := set(values) - (allowed | {NONE}):
        raise HTTPException(
            status_code=422,
            detail={"error": {
                "code": "INVALID_POLYGON_FILTER",
                "message": f"Ungültiger Wert für {field}.",
                "values": sorted(invalid),
            }},
        )
    if NONE in values and len(values) > 1:
        raise HTTPException(
            status_code=422,
            detail={"error": {
                "code": "INVALID_POLYGON_FILTER",
                "message": f"NONE kann nicht mit einem Wert für {field} kombiniert werden.",
                "values": sorted(values),
            }},
        )
    return values


@dataclass(frozen=True, slots=True)
class PolygonFilterParams:
    categories: tuple[str, ...] = ()
    floors: tuple[str, ...] = ()
    area_sizes: tuple[str, ...] = ()
    occupancy_statuses: tuple[str, ...] = ()
    business_structures: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    def cache_params(self) -> dict[str, tuple[str, ...]]:
        return {
            "categories": self.categories,
            "floors": self.floors,
            "area_sizes": self.area_sizes,
            "occupancy_statuses": self.occupancy_statuses,
            "business_structures": self.business_structures,
            "sources": self.sources,
        }


def polygon_filter_query(
    categories: Annotated[list[str] | None, Query(
        description="Branchen. Fehlend bedeutet alle, NONE bedeutet keine; mehrere Werte per CSV oder Wiederholung.",
        examples=["fashion,gastronomy"],
    )] = None,
    floors: Annotated[list[str] | None, Query(
        description="Etagen-Gruppen (UG, EG, OG). Fehlend bedeutet alle, NONE bedeutet keine.",
        examples=["EG,OG"],
    )] = None,
    area_sizes: Annotated[list[str] | None, Query(
        description="Größenklassen (S, M, L, XL). Fehlend bedeutet alle, NONE bedeutet keine.",
        examples=["S,M"],
    )] = None,
    occupancy_statuses: Annotated[list[str] | None, Query(
        description="Belegungsstatus. Fehlend bedeutet alle, NONE bedeutet keine.",
        examples=["OCCUPIED,VACANT"],
    )] = None,
    business_structures: Annotated[list[str] | None, Query(
        description="Betriebsformen. Fehlend bedeutet alle, NONE bedeutet keine.",
        examples=["CHAIN,INDEPENDENT"],
    )] = None,
    sources: Annotated[list[str] | None, Query(
        description="Datenquellen (STADTPLANNER, OSM). Fehlend bedeutet beide, NONE bedeutet keine.",
        examples=["STADTPLANNER,OSM"],
    )] = None,
) -> PolygonFilterParams:
    """Parse the established CSV query form and repeated query parameters alike."""
    parsed_sources = _values(sources, DATA_SOURCES, "sources")
    return PolygonFilterParams(
        categories=_values(categories, CATEGORIES, "categories"),
        floors=_values(floors, FLOORS, "floors"),
        area_sizes=_values(area_sizes, AREA_SIZES, "area_sizes"),
        occupancy_statuses=_values(occupancy_statuses, OCCUPANCY_STATUSES, "occupancy_statuses"),
        business_structures=_values(business_structures, BUSINESS_STRUCTURES, "business_structures"),
        sources=parsed_sources,
    )

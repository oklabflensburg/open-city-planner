from dataclasses import dataclass

from app.schemas.polygon_filters import (
    AREA_SIZES,
    BUSINESS_STRUCTURES,
    CATEGORIES,
    DATA_SOURCES,
    FLOORS,
    OCCUPANCY_STATUSES,
)


@dataclass(frozen=True, slots=True)
class SearchCatalog:
    area_types: tuple[str, ...]
    categories: tuple[str, ...]
    occupancy_statuses: tuple[str, ...]
    floors: tuple[str, ...]
    area_sizes: tuple[str, ...]
    business_structures: tuple[str, ...]
    sources: tuple[str, ...]
    category_synonyms: dict[str, tuple[str, ...]]
    allowed_operations: tuple[str, ...]


SEARCH_CATALOG = SearchCatalog(
    area_types=("MUNICIPALITY", "DISTRICT", "QUARTER"),
    categories=tuple(sorted(CATEGORIES - {"__none__"})),
    occupancy_statuses=tuple(sorted(OCCUPANCY_STATUSES)),
    floors=tuple(sorted(FLOORS)),
    area_sizes=tuple(sorted(AREA_SIZES)),
    business_structures=tuple(sorted(BUSINESS_STRUCTURES)),
    sources=tuple(sorted(DATA_SOURCES)),
    category_synonyms={
        "gastronomy": (
            "gastronomie", "gastronomiefläche", "gastronomieflächen",
            "gastronomiebetrieb", "gastronomiebetriebe", "gaststätte",
            "gaststätten", "restaurant", "restaurants", "café", "cafés", "cafe",
            "cafes", "kneipe", "kneipen", "bar", "bars",
        ),
    },
    allowed_operations=(
        "analysis_areas.list",
        "analysis_areas.geojson",
        "analysis_areas.detail",
        "analysis_areas.analytics",
        "analysis_areas.comparison",
        "analysis_areas.statistics",
        "analytics.overview",
        "analytics.compare",
        "polygons.public",
        "osm.public",
        "data_sources.status",
    ),
)


AREA_TYPE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "MUNICIPALITY": ("gemeinde", "gemeinden", "stadt", "gesamtstadt"),
    "DISTRICT": ("stadtteil", "stadtteile", "bezirk", "bezirke"),
    "QUARTER": ("quartier", "quartiere", "viertel"),
}

VACANCY_SYNONYMS = (
    "leerstand", "leerstände", "leer", "leerstehend", "leerstehende", "leerstehenden",
    "unvermietet",
)

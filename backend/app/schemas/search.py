from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.polygon_filters import (
    AREA_SIZES,
    BUSINESS_STRUCTURES,
    CATEGORIES,
    DATA_SOURCES,
    FLOORS,
    OCCUPANCY_STATUSES,
)


class SearchIntent(StrEnum):
    SHOW_AREA = "SHOW_AREA"
    SHOW_ANALYSIS_AREAS = "SHOW_ANALYSIS_AREAS"
    SHOW_FEATURES = "SHOW_FEATURES"
    CHANGE_FILTERS = "CHANGE_FILTERS"
    COUNT_FEATURES = "COUNT_FEATURES"
    ASK_ANALYTICS = "ASK_ANALYTICS"
    COMPARE_AREA = "COMPARE_AREA"


class SearchMapActionType(StrEnum):
    NONE = "NONE"
    FIT_AREA = "FIT_AREA"
    SHOW_ANALYSIS_AREAS = "SHOW_ANALYSIS_AREAS"
    REPLACE_SEARCH_LAYER = "REPLACE_SEARCH_LAYER"
    UPDATE_FILTERS = "UPDATE_FILTERS"


class SearchGeometryFilter(StrEnum):
    ALL = "ALL"
    POINTS_ONLY = "POINTS_ONLY"
    POLYGONS_ONLY = "POLYGONS_ONLY"


class SearchAreaType(StrEnum):
    MUNICIPALITY = "MUNICIPALITY"
    DISTRICT = "DISTRICT"
    QUARTER = "QUARTER"


class SearchArea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    slug: str
    area_type: SearchAreaType


OsmAmenity = Annotated[str, Field(pattern=r"^[a-z0-9_:-]{1,50}$")]


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[str] = Field(default_factory=list)
    occupancy_statuses: list[str] = Field(default_factory=list)
    floors: list[str] = Field(default_factory=list)
    area_sizes: list[str] = Field(default_factory=list)
    business_structures: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    @field_validator("categories")
    @classmethod
    def valid_categories(cls, values: list[str]) -> list[str]:
        return _allowlisted(values, (CATEGORIES - {"__none__"}) | {"NONE"}, "categories")

    @field_validator("occupancy_statuses")
    @classmethod
    def valid_statuses(cls, values: list[str]) -> list[str]:
        return _allowlisted(values, OCCUPANCY_STATUSES | {"NONE"}, "occupancy_statuses")

    @field_validator("floors")
    @classmethod
    def valid_floors(cls, values: list[str]) -> list[str]:
        return _allowlisted(values, FLOORS | {"NONE"}, "floors")

    @field_validator("area_sizes")
    @classmethod
    def valid_area_sizes(cls, values: list[str]) -> list[str]:
        return _allowlisted(values, AREA_SIZES | {"NONE"}, "area_sizes")

    @field_validator("business_structures")
    @classmethod
    def valid_business_structures(cls, values: list[str]) -> list[str]:
        return _allowlisted(values, BUSINESS_STRUCTURES | {"NONE"}, "business_structures")

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, values: list[str]) -> list[str]:
        return _allowlisted(values, DATA_SOURCES | {"NONE"}, "sources")


class SearchPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SearchMapActionType = SearchMapActionType.NONE
    fit_bounds: bool = False


class SearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: SearchIntent
    area: SearchArea | None = None
    area_type: SearchAreaType | None = None
    filters: SearchFilters = Field(default_factory=SearchFilters)
    geometry_filter: SearchGeometryFilter = SearchGeometryFilter.ALL
    osm_amenities: list[OsmAmenity] = Field(default_factory=list, max_length=10)
    map_action: SearchPresentation = Field(default_factory=SearchPresentation)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class SearchInterpretResponse(BaseModel):
    query: str
    plan: SearchPlan
    resolved: bool = True
    warnings: list[str] = Field(default_factory=list)


class SearchMapAction(BaseModel):
    type: SearchMapActionType
    fit_bounds: bool = False
    bounds: tuple[float, float, float, float] | None = None


class SearchResponse(BaseModel):
    query: str
    plan: SearchPlan
    answer: str
    map_action: SearchMapAction
    data: Any = None
    warnings: list[str] = Field(default_factory=list)


def _allowlisted(values: list[str], allowed: frozenset[str], field: str) -> list[str]:
    unique = list(dict.fromkeys(values))
    invalid = set(unique) - allowed
    if invalid:
        raise ValueError(f"Ungültige Werte für {field}: {', '.join(sorted(invalid))}")
    if "NONE" in unique and len(unique) > 1:
        raise ValueError(f"NONE kann für {field} nicht mit anderen Werten kombiniert werden")
    return unique

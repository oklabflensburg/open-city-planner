from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.analysis_area import AnalysisAreaAnalytics, AnalysisAreaDetail, AnalysisAreaPolygon
from app.schemas.analytics import AreaCompareResult, LocationAnalysis
from app.schemas.geojson import PublicPolygonDetail
from app.schemas.search import (
    OsmAmenity,
    SearchArea,
    SearchAreaType,
    SearchFilters,
    SearchGeometryFilter,
)
from app.schemas.statistics import (
    AreaStatisticSeriesRead,
    AreaStatisticsRead,
    StatisticsDataSourceStatus,
)


class AssistantToolName(StrEnum):
    RESOLVE_AREA = "resolve_area"
    LIST_AREAS = "list_areas"
    GET_AREA_DETAIL = "get_area_detail"
    GET_AREA_ANALYTICS = "get_area_analytics"
    GET_AREA_STATISTICS = "get_area_statistics"
    GET_STATISTIC_SERIES = "get_statistic_series"
    COMPARE_AREAS = "compare_areas"
    LIST_AREA_POLYGONS = "list_area_polygons"
    GET_POLYGON_DETAIL = "get_polygon_detail"
    GET_POLYGON_LOCATION = "get_polygon_location"
    SEARCH_FEATURES = "search_features"
    GET_DATA_SOURCE_STATUS = "get_data_source_status"
    SEARCH_KNOWLEDGE = "search_knowledge"
    GET_CONCEPT = "get_concept"
    DESCRIBE_CATEGORY = "describe_category"
    DESCRIBE_METRIC = "describe_metric"
    DESCRIBE_FILTER = "describe_filter"
    LIST_KNOWN_DATASETS = "list_known_datasets"
    GET_OSM_FEATURE_DETAIL = "get_osm_feature_detail"


class AssistantIntent(StrEnum):
    ANSWER_QUESTION = "ANSWER_QUESTION"
    COMPARE_AREAS = "COMPARE_AREAS"
    SHOW_FEATURES = "SHOW_FEATURES"
    CHANGE_FILTERS = "CHANGE_FILTERS"
    LIST_AREAS = "LIST_AREAS"
    UNSUPPORTED = "UNSUPPORTED"


class AssistantResponseMode(StrEnum):
    ANSWER = "ANSWER"
    CLARIFICATION = "CLARIFICATION"
    REFUSAL = "REFUSAL"


class AssistantPresentationBehavior(StrEnum):
    KEEP_OPEN = "KEEP_OPEN"
    AUTO_CLOSE = "AUTO_CLOSE"
    COLLAPSE = "COLLAPSE"


class AnswerPresentationType(StrEnum):
    TEXT = "TEXT"
    METRIC = "METRIC"
    METRIC_LIST = "METRIC_LIST"
    COMPARISON = "COMPARISON"
    AREA_LIST = "AREA_LIST"
    FEATURE_LIST = "FEATURE_LIST"
    KNOWLEDGE = "KNOWLEDGE"
    DATA_SOURCE_STATUS = "DATA_SOURCE_STATUS"


class AssistantViewport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    zoom: float = Field(ge=0, le=24)

    @field_validator("east")
    @classmethod
    def east_must_follow_west(cls, value: float, info: Any) -> float:
        west = info.data.get("west")
        if west is not None and value <= west:
            raise ValueError("east muss größer als west sein")
        return value

    @field_validator("north")
    @classmethod
    def north_must_follow_south(cls, value: float, info: Any) -> float:
        south = info.data.get("south")
        if south is not None and value <= south:
            raise ValueError("north muss größer als south sein")
        return value


class SelectedOsmFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    osm_type: Literal["node", "way", "relation"]
    osm_id: int = Field(gt=0)


class AssistantMapActionType(StrEnum):
    FIT_AREA = "FIT_AREA"
    SHOW_ANALYSIS_AREAS = "SHOW_ANALYSIS_AREAS"
    HIGHLIGHT_AREAS = "HIGHLIGHT_AREAS"
    REPLACE_SEARCH_LAYER = "REPLACE_SEARCH_LAYER"
    UPDATE_FILTERS = "UPDATE_FILTERS"


class AssistantContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_area: SearchArea | None = None
    active_filters: SearchFilters = Field(default_factory=SearchFilters)
    last_compared_areas: list[SearchArea] = Field(default_factory=list, max_length=4)
    last_intent: AssistantIntent | None = None
    last_topic: str | None = Field(default=None, max_length=50)
    selected_polygon_slug: str | None = Field(
        default=None, min_length=1, max_length=255, pattern=r"^[a-z0-9][a-z0-9_-]*$"
    )
    selected_osm_feature: SelectedOsmFeature | None = None
    viewport: AssistantViewport | None = None

    @field_validator("last_topic", mode="before")
    @classmethod
    def discard_legacy_oversized_topic(cls, value: Any) -> Any:
        # Frühere Versionen haben die Antwortmeldung versehentlich als Topic
        # zurückgegeben. Bereits geöffnete Clients dürfen diesen Altzustand
        # verlustfrei verwerfen, statt dauerhaft mit HTTP 422 festzuhängen.
        if isinstance(value, str) and len(value) > 50:
            return None
        return value


class AssistantQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=500)
    context: AssistantContext = Field(default_factory=AssistantContext)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class AssistantStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: AssistantToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


class AssistantPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: AssistantIntent
    steps: list[AssistantStep] = Field(default_factory=list, max_length=16)
    response_mode: AssistantResponseMode = AssistantResponseMode.ANSWER


class AssistantCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    slug: str | None = None
    source: str | None = None
    period: str | None = None
    inherited_from_parent: bool | None = None


class AnswerPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: AnswerPresentationType
    title: str
    value: int | float | str | None = None
    unit: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


class AssistantMapAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: AssistantMapActionType
    area_slug: str | None = None
    area_slugs: list[str] = Field(default_factory=list, max_length=4)
    area_type: SearchAreaType | None = None
    fit_bounds: bool = False
    bounds: tuple[float, float, float, float] | None = None
    feature_collection: dict[str, Any] | None = None
    filters: SearchFilters | None = None
    geometry_filter: SearchGeometryFilter | None = None


class AssistantSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    area_slug: str | None = None
    updated_at: str | None = None
    source: str | None = None
    period: str | None = None
    inherited_from_parent: bool | None = None
    knowledge_key: str | None = None


class AssistantEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    field: str | None = None
    area_slug: str | None = None
    knowledge_key: str | None = None
    osm_type: Literal["node", "way", "relation"] | None = None
    osm_id: int | None = None


class AssistantClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence: list[AssistantEvidence] = Field(default_factory=list, max_length=8)


class AssistantFollowUpAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "SHOW_ON_MAP", "COMPARE_WITH_AREA", "EXPLAIN_CONCEPT",
        "SHOW_STATISTICS", "SHOW_DATA_SOURCE",
    ]
    label: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=2, max_length=500)


class AssistantTelemetry(BaseModel):
    llm_used: bool = False
    model: str | None = None
    tool_calls: int = Field(ge=0, le=4)
    duration_ms: int = Field(ge=0)
    intent: AssistantIntent
    success: bool
    provider: str | None = None
    prompt_version: str | None = None
    knowledge_version: str | None = None
    tool_registry_version: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AssistantQueryResponse(BaseModel):
    query: str
    answer: str
    plan: AssistantPlan
    presentation: AnswerPresentation
    citations: list[AssistantCitation] = Field(default_factory=list)
    sources_used: list[AssistantSource] = Field(default_factory=list)
    map_actions: list[AssistantMapAction] = Field(default_factory=list)
    context: AssistantContext
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    claims: list[AssistantClaim] = Field(default_factory=list)
    follow_up_actions: list[AssistantFollowUpAction] = Field(default_factory=list)
    presentation_behavior: AssistantPresentationBehavior = (
        AssistantPresentationBehavior.KEEP_OPEN
    )
    telemetry: AssistantTelemetry


class ResolveAreaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_or_slug: str = Field(min_length=1, max_length=200)


class ResolveAreaResult(BaseModel):
    status: Literal["resolved", "ambiguous", "not_found"]
    area: SearchArea | None = None
    candidates: list[SearchArea] = Field(default_factory=list)


class AreaListResult(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


class ToolDataResult(BaseModel):
    data: Any = None


class AreaDetailToolResult(BaseModel):
    data: AnalysisAreaDetail


class AreaAnalyticsToolResult(BaseModel):
    data: AnalysisAreaAnalytics


class AreaStatisticsToolResult(BaseModel):
    data: AreaStatisticsRead


class StatisticSeriesToolResult(BaseModel):
    data: AreaStatisticSeriesRead


class CompareAreasToolResult(BaseModel):
    data: AreaCompareResult


class AssistantSearchFeature(BaseModel):
    type: Literal["Feature"]
    id: str | None = None
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "Point", "MultiPoint", "LineString", "MultiLineString",
            "Polygon", "MultiPolygon", "GeometryCollection",
        }
        if value.get("type") not in allowed:
            raise ValueError("Nicht unterstützter GeoJSON-Geometrietyp")
        if value.get("type") == "GeometryCollection":
            if not isinstance(value.get("geometries"), list):
                raise ValueError("Für GeometryCollection fehlen Geometrien")
        elif "coordinates" not in value:
            raise ValueError("Für die GeoJSON-Geometrie fehlen Koordinaten")
        return value


class AssistantSearchFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[AssistantSearchFeature] = Field(max_length=200)


class FeatureSearchData(BaseModel):
    feature_collection: AssistantSearchFeatureCollection
    bounds: tuple[float, float, float, float] | None = None


class AreaPolygonsToolResult(BaseModel):
    data: list[AnalysisAreaPolygon] | FeatureSearchData


class PolygonDetailToolResult(BaseModel):
    data: PublicPolygonDetail


class PolygonLocationToolResult(BaseModel):
    data: LocationAnalysis


class SearchFeaturesToolResult(BaseModel):
    data: FeatureSearchData


class DataSourceStatusToolResult(BaseModel):
    data: list[StatisticsDataSourceStatus]


class ListAreasInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area_type: SearchAreaType | None = None
    parent_slug: str | None = Field(default=None, max_length=255)


class AreaSlugInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=255)


class AreaAnalyticsInput(AreaSlugInput):
    filters: SearchFilters = Field(default_factory=SearchFilters)


class StatisticSeriesInput(AreaSlugInput):
    metric_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,99}$")


class CompareAreasInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area_slugs: list[str] = Field(min_length=2, max_length=4)
    include_municipality_benchmark: bool = True
    filters: SearchFilters = Field(default_factory=SearchFilters)


class ListAreaPolygonsInput(AreaAnalyticsInput):
    limit: int = Field(default=24, ge=1, le=200)


class PolygonLocationInput(AreaSlugInput):
    radius_m: int = Field(default=500, ge=100, le=2000)


class SearchFeaturesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area_slug: str = Field(min_length=1, max_length=255)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    geometry_filter: SearchGeometryFilter = SearchGeometryFilter.ALL
    osm_amenities: list[OsmAmenity] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=200, ge=1, le=200)


class EmptyToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeKeyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")


class CategoryKnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,49}$")


class MetricKnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,99}$")


class FilterKnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filter: Literal[
        "categories", "occupancy_statuses", "floors", "area_sizes",
        "business_structures", "sources",
    ]


class OsmFeatureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    osm_type: Literal["node", "way", "relation"]
    osm_id: int = Field(gt=0)


class KnowledgeToolResult(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=10)


class OsmFeatureToolResult(BaseModel):
    data: dict[str, Any]

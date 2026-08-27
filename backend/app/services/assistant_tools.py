from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis_areas.application.legacy_queries import (
    area_analytics,
    area_detail_by_slug,
    area_polygons_by_slug,
    area_uuid_by_slug,
    list_areas,
)
from app.schemas.analytics import AreaCompareFilters, AreaCompareRequest
from app.schemas.assistant import (
    AreaAnalyticsInput,
    AreaAnalyticsToolResult,
    AreaDetailToolResult,
    AreaListResult,
    AreaPolygonsToolResult,
    AreaSlugInput,
    AreaStatisticsToolResult,
    AssistantToolName,
    CategoryKnowledgeInput,
    CompareAreasInput,
    CompareAreasToolResult,
    DataSourceStatusToolResult,
    EmptyToolInput,
    FilterKnowledgeInput,
    KnowledgeKeyInput,
    KnowledgeSearchInput,
    KnowledgeToolResult,
    ListAreaPolygonsInput,
    ListAreasInput,
    MetricKnowledgeInput,
    OsmFeatureInput,
    OsmFeatureToolResult,
    PolygonDetailToolResult,
    PolygonLocationInput,
    PolygonLocationToolResult,
    ResolveAreaInput,
    ResolveAreaResult,
    SearchFeaturesInput,
    SearchFeaturesToolResult,
    StatisticSeriesInput,
    StatisticSeriesToolResult,
)
from app.schemas.search import (
    SearchArea,
    SearchAreaType,
    SearchIntent,
    SearchMapActionType,
    SearchPlan,
    SearchPresentation,
)
from app.services.analytics import compare_areas
from app.services.area_statistics import (
    area_statistic_series,
    area_statistics,
    statistics_source_status,
)
from app.services.assistant_explanations import explain_osm_feature
from app.services.assistant_knowledge import (
    KNOWLEDGE_CATALOG,
    get_knowledge,
    public_datasets,
    retrieve_knowledge,
)
from app.services.location_analytics import polygon_location_analysis
from app.services.osm_features import osm_feature_detail
from app.services.polygons import public_polygon_by_slug
from app.services.search_executor import execute_search
from app.services.search_interpreter import normalize_search_text

MAX_ASSISTANT_TOOL_CALLS = 4
MAX_TOOL_FEATURES = 200


class AssistantToolError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


ToolExecutor = Callable[[AsyncSession, BaseModel], Awaitable[BaseModel]]


@dataclass(frozen=True, slots=True)
class AssistantTool:
    name: AssistantToolName
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    executor: ToolExecutor
    public_contract: str


async def _resolve_area(session: AsyncSession, raw: BaseModel) -> ResolveAreaResult:
    args = ResolveAreaInput.model_validate(raw)
    value = normalize_search_text(args.name_or_slug)
    all_rows = await list_areas(session)
    rows = [row for row in all_rows if row.name.strip().casefold() == args.name_or_slug.strip().casefold()]
    if not rows:
        rows = [row for row in all_rows if row.slug.casefold() == args.name_or_slug.strip().casefold()]
    if not rows:
        rows = [row for row in all_rows if normalize_search_text(row.name) == value]
    candidates = [SearchArea(id=row.id, slug=row.slug, name=row.name, area_type=SearchAreaType(row.area_type)) for row in rows]
    if not candidates:
        return ResolveAreaResult(status="not_found")
    if len(candidates) > 1:
        return ResolveAreaResult(status="ambiguous", candidates=candidates[:8])
    return ResolveAreaResult(status="resolved", area=candidates[0])


async def _list_areas(session: AsyncSession, raw: BaseModel) -> AreaListResult:
    args = ListAreasInput.model_validate(raw)
    parent_id = None
    if args.parent_slug:
        parent_id = await area_uuid_by_slug(session, args.parent_slug)
        if parent_id is None:
            raise AssistantToolError("AREA_NOT_FOUND", "Das übergeordnete Gebiet wurde nicht gefunden.", 404)
    rows = await list_areas(session, args.area_type.value if args.area_type else None, parent_id)
    return AreaListResult(items=[row.model_dump(mode="json") for row in rows[:200]])


async def _area_detail(session: AsyncSession, raw: BaseModel) -> AreaDetailToolResult:
    args = AreaSlugInput.model_validate(raw)
    result = await area_detail_by_slug(session, args.slug)
    if result is None:
        raise AssistantToolError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
    return AreaDetailToolResult(data=result)


def _filter_kwargs(filters: Any) -> dict[str, tuple[str, ...]]:
    def values(name: str) -> tuple[str, ...]:
        return tuple(value for value in getattr(filters, name) if value != "NONE")
    return {name: values(name) for name in (
        "categories", "floors", "area_sizes", "occupancy_statuses",
        "business_structures", "sources",
    )}


async def _area_analytics(session: AsyncSession, raw: BaseModel) -> AreaAnalyticsToolResult:
    args = AreaAnalyticsInput.model_validate(raw)
    area_id = await area_uuid_by_slug(session, args.slug)
    if area_id is None:
        raise AssistantToolError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
    result = await area_analytics(session, area_id, **_filter_kwargs(args.filters))
    if result is None:
        raise AssistantToolError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
    return AreaAnalyticsToolResult(data=result)


async def _area_statistics(session: AsyncSession, raw: BaseModel) -> AreaStatisticsToolResult:
    args = AreaSlugInput.model_validate(raw)
    result = await area_statistics(session, args.slug)
    if result is None:
        raise AssistantToolError("STATISTICS_NOT_FOUND", "Für das Gebiet liegen keine Statistiken vor.", 404)
    return AreaStatisticsToolResult(data=result)


async def _statistic_series(session: AsyncSession, raw: BaseModel) -> StatisticSeriesToolResult:
    args = StatisticSeriesInput.model_validate(raw)
    result = await area_statistic_series(session, args.slug, args.metric_key)
    if result is None:
        raise AssistantToolError("STATISTIC_NOT_FOUND", "Die Statistik-Zeitreihe wurde nicht gefunden.", 404)
    return StatisticSeriesToolResult(data=result)


async def _compare_areas(session: AsyncSession, raw: BaseModel) -> CompareAreasToolResult:
    args = CompareAreasInput.model_validate(raw)
    result = await compare_areas(session, AreaCompareRequest(
        area_slugs=args.area_slugs,
        include_municipality_benchmark=args.include_municipality_benchmark,
        filters=AreaCompareFilters(**args.filters.model_dump()),
    ))
    return CompareAreasToolResult(data=result)


async def _area_polygons(session: AsyncSession, raw: BaseModel) -> AreaPolygonsToolResult:
    args = ListAreaPolygonsInput.model_validate(raw)
    if any(args.filters.model_dump().values()):
        feature_args = SearchFeaturesInput(
            area_slug=args.slug, filters=args.filters, geometry_filter="POLYGONS_ONLY", limit=args.limit
        )
        result = await _search_features(session, feature_args)
        return AreaPolygonsToolResult(data=result.data)
    result = await area_polygons_by_slug(session, args.slug, min(args.limit, 24))
    if result is None:
        raise AssistantToolError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
    return AreaPolygonsToolResult(data=result)


async def _polygon_detail(session: AsyncSession, raw: BaseModel) -> PolygonDetailToolResult:
    args = AreaSlugInput.model_validate(raw)
    result = await public_polygon_by_slug(session, args.slug)
    if result is None:
        raise AssistantToolError("POLYGON_NOT_FOUND", "Die Fläche wurde nicht gefunden.", 404)
    return PolygonDetailToolResult(data=result)


async def _polygon_location(session: AsyncSession, raw: BaseModel) -> PolygonLocationToolResult:
    args = PolygonLocationInput.model_validate(raw)
    result = await polygon_location_analysis(session, slug=args.slug, radius_m=args.radius_m)
    if result is None:
        raise AssistantToolError("POLYGON_NOT_FOUND", "Die Fläche wurde nicht gefunden.", 404)
    return PolygonLocationToolResult(data=result)


async def _search_features(session: AsyncSession, raw: BaseModel) -> SearchFeaturesToolResult:
    args = SearchFeaturesInput.model_validate(raw)
    detail = await area_detail_by_slug(session, args.area_slug)
    if detail is None:
        raise AssistantToolError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
    area = SearchArea(id=detail.id, slug=detail.slug, name=detail.name, area_type=SearchAreaType(detail.area_type))
    plan = SearchPlan(
        intent=SearchIntent.SHOW_FEATURES,
        area=area,
        filters=args.filters,
        geometry_filter=args.geometry_filter,
        osm_amenities=args.osm_amenities,
        area_m2_greater_than=args.area_m2_greater_than,
        area_m2_less_than=args.area_m2_less_than,
        map_action=SearchPresentation(type=SearchMapActionType.REPLACE_SEARCH_LAYER, fit_bounds=True),
    )
    response = await execute_search(session, "Assistant-Feature-Suche", plan)
    data = response.data
    if isinstance(data, dict) and isinstance(data.get("features"), list):
        data["features"] = data["features"][: min(args.limit, MAX_TOOL_FEATURES)]
    return SearchFeaturesToolResult(data={
        "feature_collection": data,
        "bounds": response.map_action.bounds,
    })


async def _data_source_status(session: AsyncSession, raw: BaseModel) -> DataSourceStatusToolResult:
    EmptyToolInput.model_validate(raw)
    result = await statistics_source_status(session)
    return DataSourceStatusToolResult(data=[result])


async def _search_knowledge(_session: AsyncSession, raw: BaseModel) -> KnowledgeToolResult:
    args = KnowledgeSearchInput.model_validate(raw)
    return KnowledgeToolResult(items=[
        match.entry.public_dict(confidence=match.confidence)
        for match in retrieve_knowledge(args.query, args.limit)
    ])


async def _get_concept(_session: AsyncSession, raw: BaseModel) -> KnowledgeToolResult:
    args = KnowledgeKeyInput.model_validate(raw)
    entry = get_knowledge(args.key)
    if entry is None:
        raise AssistantToolError(
            "ASSISTANT_KNOWLEDGE_NOT_FOUND", "Der Fachbegriff wurde nicht gefunden.", 404
        )
    return KnowledgeToolResult(items=[entry.public_dict()])


async def _describe_category(_session: AsyncSession, raw: BaseModel) -> KnowledgeToolResult:
    args = CategoryKnowledgeInput.model_validate(raw)
    return await _get_concept(_session, KnowledgeKeyInput(key=f"category.{args.category}"))


async def _describe_metric(_session: AsyncSession, raw: BaseModel) -> KnowledgeToolResult:
    args = MetricKnowledgeInput.model_validate(raw)
    return await _get_concept(_session, KnowledgeKeyInput(key=f"metric.{args.metric_key}"))


async def _describe_filter(_session: AsyncSession, raw: BaseModel) -> KnowledgeToolResult:
    args = FilterKnowledgeInput.model_validate(raw)
    prefixes = {
        "categories": "category.",
        "occupancy_statuses": "occupancy.",
        "floors": "filter.floor.",
        "business_structures": "filter.business_structure.",
        "sources": "data_source.",
        "area_sizes": "filter.area_size.",
    }
    entries = [
        entry.public_dict() for entry in KNOWLEDGE_CATALOG
        if entry.key.startswith(prefixes[args.filter])
    ]
    return KnowledgeToolResult(items=entries[:10])


async def _list_known_datasets(_session: AsyncSession, raw: BaseModel) -> KnowledgeToolResult:
    EmptyToolInput.model_validate(raw)
    return KnowledgeToolResult(items=public_datasets())


async def _osm_feature_detail(session: AsyncSession, raw: BaseModel) -> OsmFeatureToolResult:
    args = OsmFeatureInput.model_validate(raw)
    result = await osm_feature_detail(session, osm_type=args.osm_type, osm_id=args.osm_id)
    if result is None:
        raise AssistantToolError("OSM_FEATURE_NOT_FOUND", "Das OSM-Objekt wurde nicht gefunden.", 404)
    return OsmFeatureToolResult(data=explain_osm_feature(result.model_dump(mode="json")))


def _tool(name: AssistantToolName, description: str, input_model: type[BaseModel], output_model: type[BaseModel], executor: ToolExecutor, contract: str) -> AssistantTool:
    return AssistantTool(name, description, input_model, output_model, executor, contract)


ASSISTANT_TOOL_REGISTRY: dict[AssistantToolName, AssistantTool] = {
    tool.name: tool for tool in (
        _tool(AssistantToolName.RESOLVE_AREA, "Gebiet eindeutig auflösen", ResolveAreaInput, ResolveAreaResult, _resolve_area, "GET /analysis-areas"),
        _tool(AssistantToolName.LIST_AREAS, "Gebiete oder Kinder auflisten", ListAreasInput, AreaListResult, _list_areas, "GET /analysis-areas"),
        _tool(AssistantToolName.GET_AREA_DETAIL, "Öffentliche Gebietsdetails laden", AreaSlugInput, AreaDetailToolResult, _area_detail, "GET /analysis-areas/by-slug/{slug}"),
        _tool(AssistantToolName.GET_AREA_ANALYTICS, "Gefilterte Gebietskennzahlen laden", AreaAnalyticsInput, AreaAnalyticsToolResult, _area_analytics, "GET /analysis-areas/{id}/analytics"),
        _tool(AssistantToolName.GET_AREA_STATISTICS, "Kommunale Gebietsstatistik laden", AreaSlugInput, AreaStatisticsToolResult, _area_statistics, "GET /analysis-areas/by-slug/{slug}/statistics"),
        _tool(AssistantToolName.GET_STATISTIC_SERIES, "Statistik-Zeitreihe laden", StatisticSeriesInput, StatisticSeriesToolResult, _statistic_series, "GET /analysis-areas/by-slug/{slug}/statistics/{metric_key}"),
        _tool(AssistantToolName.COMPARE_AREAS, "Bis zu vier Gebiete vergleichen", CompareAreasInput, CompareAreasToolResult, _compare_areas, "POST /analytics/compare (read-only)"),
        _tool(AssistantToolName.LIST_AREA_POLYGONS, "Verkaufsflächen eines Gebiets laden", ListAreaPolygonsInput, AreaPolygonsToolResult, _area_polygons, "GET /analysis-areas/by-slug/{slug}/polygons"),
        _tool(AssistantToolName.GET_POLYGON_DETAIL, "Öffentliche Flächendetails laden", AreaSlugInput, PolygonDetailToolResult, _polygon_detail, "GET /polygons/by-slug/{slug}"),
        _tool(AssistantToolName.GET_POLYGON_LOCATION, "POIs im kontrollierten Umkreis laden", PolygonLocationInput, PolygonLocationToolResult, _polygon_location, "GET /polygons/by-slug/{slug}/location"),
        _tool(AssistantToolName.SEARCH_FEATURES, "Kartenobjekte exakt innerhalb eines Gebiets suchen", SearchFeaturesInput, SearchFeaturesToolResult, _search_features, "GET /osm/features + GET /polygons/overview"),
        _tool(AssistantToolName.GET_DATA_SOURCE_STATUS, "Öffentlichen Datenquellenstatus laden", EmptyToolInput, DataSourceStatusToolResult, _data_source_status, "GET /data-sources/status"),
        _tool(AssistantToolName.SEARCH_KNOWLEDGE, "Kontrolliertes Fachwissen durchsuchen", KnowledgeSearchInput, KnowledgeToolResult, _search_knowledge, "STATIC KnowledgeCatalog"),
        _tool(AssistantToolName.GET_CONCEPT, "Fachbegriff anhand seines Schlüssels beschreiben", KnowledgeKeyInput, KnowledgeToolResult, _get_concept, "STATIC KnowledgeCatalog"),
        _tool(AssistantToolName.DESCRIBE_CATEGORY, "Kanonische Kategorie erklären", CategoryKnowledgeInput, KnowledgeToolResult, _describe_category, "STATIC KnowledgeCatalog"),
        _tool(AssistantToolName.DESCRIBE_METRIC, "Öffentliche Kennzahl erklären", MetricKnowledgeInput, KnowledgeToolResult, _describe_metric, "STATIC KnowledgeCatalog"),
        _tool(AssistantToolName.DESCRIBE_FILTER, "Öffentliche Filterwerte erklären", FilterKnowledgeInput, KnowledgeToolResult, _describe_filter, "STATIC KnowledgeCatalog"),
        _tool(AssistantToolName.LIST_KNOWN_DATASETS, "Öffentliche Fachdatenquellen auflisten", EmptyToolInput, KnowledgeToolResult, _list_known_datasets, "STATIC KnowledgeCatalog"),
        _tool(AssistantToolName.GET_OSM_FEATURE_DETAIL, "OSM-Kategorie und Belegungsstatus deterministisch erklären", OsmFeatureInput, OsmFeatureToolResult, _osm_feature_detail, "GET /osm/features/{osm_type}/{osm_id}"),
    )
}


async def execute_assistant_tool(session: AsyncSession, name: AssistantToolName, arguments: dict[str, Any]) -> BaseModel:
    tool = ASSISTANT_TOOL_REGISTRY.get(name)
    if tool is None:
        raise AssistantToolError("TOOL_NOT_ALLOWED", "Dieses Tool ist nicht freigegeben.", 403)
    validated = tool.input_model.model_validate(arguments)
    result = await tool.executor(session, validated)
    return tool.output_model.model_validate(result)

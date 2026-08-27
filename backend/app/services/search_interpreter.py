import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis_areas.persistence.models import AnalysisArea
from app.schemas.search import (
    SearchArea,
    SearchAreaType,
    SearchFilters,
    SearchGeometryFilter,
    SearchIntent,
    SearchMapActionType,
    SearchPlan,
    SearchPresentation,
)
from app.services.search_catalog import (
    AREA_TYPE_SYNONYMS,
    SEARCH_CATALOG,
    VACANCY_SYNONYMS,
    SearchCatalog,
)


class SearchLLMProvider(Protocol):
    async def interpret(self, query: str, context: SearchCatalog) -> SearchPlan: ...


class SearchInterpretationError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class _AreaCandidate:
    id: str
    slug: str
    name: str
    area_type: str

    def schema(self) -> SearchArea:
        return SearchArea(
            id=self.id,
            slug=self.slug,
            name=self.name,
            area_type=SearchAreaType(self.area_type),
        )


FORBIDDEN_PATTERNS = (
    r"\b(drop|delete|truncate|insert|update|alter)\s+(table|from|into|users?)\b",
    r"\b(passw(?:or)?d|mfa|session|oauth|token)s?\b",
    r"\b(e-?mail-adressen|benutzer(?:innen)?|users?)\b",
    r"ignoriere\s+(alle|die)\s+regeln",
)


def normalize_search_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ß", "ss")
    return " ".join(re.sub(r"[^\wäöü-]+", " ", value).split())


async def resolve_analysis_area(session: AsyncSession, query: str) -> SearchArea | None:
    rows = (
        await session.execute(
            select(
                AnalysisArea.uuid.label("id"),
                AnalysisArea.slug,
                AnalysisArea.name,
                AnalysisArea.area_type,
            ).order_by(AnalysisArea.name, AnalysisArea.id)
        )
    ).mappings().all()
    candidates = [
        _AreaCandidate(
            id=str(row["id"]), slug=str(row["slug"]), name=str(row["name"]),
            area_type=str(row["area_type"]),
        )
        for row in rows
    ]
    normalized_query = normalize_search_text(query)
    raw_query = query.strip().casefold()

    exact_name = [item for item in candidates if item.name.strip().casefold() == raw_query]
    if exact_name:
        return _unique_area(exact_name)
    exact_slug = [item for item in candidates if item.slug.casefold() == raw_query]
    if exact_slug:
        return _unique_area(exact_slug)

    matches = [
        item for item in candidates
        if re.search(rf"(?<!\w){re.escape(normalize_search_text(item.name))}(?!\w)", normalized_query)
        or re.search(rf"(?<!\w){re.escape(normalize_search_text(item.slug))}(?!\w)", normalized_query)
    ]
    if not matches:
        return None
    longest = max(len(normalize_search_text(item.name)) for item in matches)
    return _unique_area([item for item in matches if len(normalize_search_text(item.name)) == longest])


def _unique_area(candidates: list[_AreaCandidate]) -> SearchArea:
    unique = {(item.id, item.slug): item for item in candidates}
    if len(unique) != 1:
        names = ", ".join(sorted({item.name for item in unique.values()}))
        raise SearchInterpretationError(
            "AMBIGUOUS_AREA",
            f"Das Gebiet ist nicht eindeutig. Mögliche Treffer: {names}.",
            409,
        )
    return next(iter(unique.values())).schema()


async def interpret_search(
    session: AsyncSession,
    query: str,
    *,
    provider: SearchLLMProvider | None = None,
) -> SearchPlan:
    normalized = normalize_search_text(query)
    if any(re.search(pattern, normalized) for pattern in FORBIDDEN_PATTERNS):
        raise SearchInterpretationError(
            "FORBIDDEN_SEARCH_INTENT",
            "Die Suche darf ausschließlich öffentliche Karten- und Analysedaten abfragen.",
            403,
        )

    area_type = _area_type(normalized)
    if area_type and _contains_any(normalized, ("alle", "anzeigen", "zeige")):
        return SearchPlan(
            intent=SearchIntent.SHOW_ANALYSIS_AREAS,
            area_type=SearchAreaType(area_type),
            map_action=SearchPresentation(type=SearchMapActionType.SHOW_ANALYSIS_AREAS, fit_bounds=True),
        )

    if _is_filter_command(normalized, VACANCY_SYNONYMS):
        return _filter_plan(occupancy_statuses=["VACANT"])
    if _is_filter_command(normalized, ("belegt", "belegte", "vermietet")):
        return _filter_plan(occupancy_statuses=["OCCUPIED"])
    if _is_filter_command(normalized, ("fläche", "flächen", "flaeche", "flaechen")):
        return _filter_plan(geometry_filter=SearchGeometryFilter.POLYGONS_ONLY)
    if _is_filter_command(normalized, ("osm", "openstreetmap")):
        return _filter_plan(sources=["OSM"])
    if _is_filter_command(normalized, ("stadtplaner",)):
        return _filter_plan(sources=["STADTPLANNER"])
    if _is_filter_command(normalized, ("erdgeschoss", "eg")):
        return _filter_plan(floors=["EG"])
    if _is_filter_command(normalized, ("ketten", "kette", "filialist", "filialisten")):
        return _filter_plan(business_structures=["CHAIN"])
    if _is_filter_command(normalized, ("inhabergeführt", "inhabergefuehrt", "unabhängig", "unabhaengig")):
        return _filter_plan(business_structures=["INDEPENDENT"])

    category = _category(normalized)
    needs_area = any(token in normalized for token in (" in ", "wie viele", "wie gross", "vergleiche"))
    area = await resolve_analysis_area(session, query)
    if area is None and needs_area:
        raise SearchInterpretationError(
            "AREA_NOT_FOUND", "Das genannte Gebiet wurde nicht gefunden.", 404
        )

    polygon_only = _contains_any(normalized, ("fläche", "flächen", "flaeche", "flaechen"))
    filters = SearchFilters(
        categories=[category] if category else [],
        sources=["OSM", "STADTPLANNER"],
    )
    geometry_filter = (
        SearchGeometryFilter.POLYGONS_ONLY if polygon_only else SearchGeometryFilter.ALL
    )

    if normalized.startswith("vergleiche") and area:
        return SearchPlan(
            intent=SearchIntent.COMPARE_AREA, area=area, filters=filters,
            map_action=SearchPresentation(type=SearchMapActionType.FIT_AREA, fit_bounds=True),
        )
    if "wie viele" in normalized and area:
        intent = SearchIntent.COUNT_FEATURES if category else SearchIntent.ASK_ANALYTICS
        return SearchPlan(
            intent=intent, area=area, filters=filters, geometry_filter=geometry_filter,
            map_action=SearchPresentation(type=SearchMapActionType.FIT_AREA, fit_bounds=True),
        )
    if _contains_any(normalized, ("wie gross", "wie groß")) and area:
        return SearchPlan(
            intent=SearchIntent.SHOW_AREA, area=area,
            map_action=SearchPresentation(type=SearchMapActionType.FIT_AREA, fit_bounds=True),
        )
    if area and (category or polygon_only):
        return SearchPlan(
            intent=SearchIntent.SHOW_FEATURES, area=area, filters=filters,
            geometry_filter=geometry_filter,
            map_action=SearchPresentation(
                type=SearchMapActionType.REPLACE_SEARCH_LAYER, fit_bounds=True
            ),
        )
    if area and _contains_any(normalized, ("zeige", "anzeigen", "karte")):
        return SearchPlan(
            intent=SearchIntent.SHOW_AREA, area=area,
            map_action=SearchPresentation(type=SearchMapActionType.FIT_AREA, fit_bounds=True),
        )
    if provider is not None:
        return SearchPlan.model_validate(
            (await provider.interpret(query, SEARCH_CATALOG)).model_dump()
        )
    raise SearchInterpretationError(
        "UNSUPPORTED_SEARCH_INTENT",
        "Diese Frage wird von der intelligenten Suche noch nicht unterstützt.",
    )


def _area_type(normalized: str) -> str | None:
    for area_type, synonyms in AREA_TYPE_SYNONYMS.items():
        if _contains_any(normalized, synonyms):
            return area_type
    return None


def _category(normalized: str) -> str | None:
    for category, synonyms in SEARCH_CATALOG.category_synonyms.items():
        if _contains_any(normalized, synonyms):
            return category
    return None


def _contains_any(normalized: str, values: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(normalize_search_text(value))}(?!\w)", normalized)
        for value in values
    )


def _is_filter_command(normalized: str, values: tuple[str, ...]) -> bool:
    return _contains_any(normalized, ("nur",)) and _contains_any(normalized, values)


def _filter_plan(
    *,
    sources: list[str] | None = None,
    occupancy_statuses: list[str] | None = None,
    floors: list[str] | None = None,
    business_structures: list[str] | None = None,
    geometry_filter: SearchGeometryFilter = SearchGeometryFilter.ALL,
) -> SearchPlan:
    return SearchPlan(
        intent=SearchIntent.CHANGE_FILTERS,
        filters=SearchFilters(
            sources=sources or [],
            occupancy_statuses=occupancy_statuses or [],
            floors=floors or [],
            business_structures=business_structures or [],
        ),
        geometry_filter=geometry_filter,
        map_action=SearchPresentation(type=SearchMapActionType.UPDATE_FILTERS),
    )

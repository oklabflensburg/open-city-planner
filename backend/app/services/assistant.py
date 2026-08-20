import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.assistant import (
    AnswerPresentation,
    AnswerPresentationSection,
    AnswerPresentationType,
    AssistantCitation,
    AssistantClaim,
    AssistantContext,
    AssistantEvidence,
    AssistantFollowUpAction,
    AssistantIntent,
    AssistantMapAction,
    AssistantMapActionType,
    AssistantPlan,
    AssistantPresentationBehavior,
    AssistantQueryRequest,
    AssistantQueryResponse,
    AssistantResponseMode,
    AssistantSource,
    AssistantStep,
    AssistantTelemetry,
    AssistantToolName,
)
from app.schemas.search import SearchArea, SearchAreaType, SearchFilters, SearchGeometryFilter
from app.services.analysis_area_api import list_areas
from app.services.assistant_knowledge import KNOWLEDGE_VERSION, retrieve_knowledge
from app.services.assistant_provider import (
    ASSISTANT_PROMPT_VERSION,
    TOOL_REGISTRY_VERSION,
    AssistantProviderError,
)
from app.services.assistant_tools import (
    ASSISTANT_TOOL_REGISTRY,
    MAX_ASSISTANT_TOOL_CALLS,
    AssistantToolError,
    execute_assistant_tool,
)
from app.services.search_catalog import SEARCH_CATALOG, VACANCY_SYNONYMS
from app.services.search_interpreter import FORBIDDEN_PATTERNS, normalize_search_text

logger = logging.getLogger(__name__)

POI_AMENITY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "townhall": ("rathaus", "rathäuser", "rathaeuser"),
    "police": ("polizei", "polizeiwache"),
    "post_office": ("postamt", "postfiliale"),
    "fire_station": ("feuerwehr", "feuerwache"),
    "school": ("schule", "schulen"),
    "kindergarten": ("kindergarten", "kindertagesstätte", "kindertagesstaette", "kita"),
    "library": ("bibliothek", "bücherei", "buecherei"),
    "hospital": ("krankenhaus", "klinik"),
    "museum": ("museum", "museen"),
}

STATISTIC_METRICS: dict[str, tuple[str, tuple[str, ...]]] = {
    "population": ("Bevölkerung", ("bevölkerung", "bevoelkerung", "einwohner", "einwohnerzahl", "bevölkerungsentwicklung", "bevoelkerungsentwicklung", "bevölkerungsdaten", "bevoelkerungsdaten")),
    "population_non_german": ("Nichtdeutsche Bevölkerung", ("nichtdeutsche bevölkerung", "nicht deutsche bevölkerung", "ausländische bevölkerung", "auslaendische bevoelkerung")),
    "age_0_17": ("Bevölkerung von 0 bis 17 Jahren", ("0 bis 17", "unter 18", "minderjährige")),
    "age_18_64": ("Bevölkerung von 18 bis 64 Jahren", ("18 bis 64", "erwerbsalter")),
    "age_65_plus": ("Bevölkerung ab 65 Jahren", ("ab 65", "über 65", "ueber 65", "senioren")),
    "households": ("Haushalte", ("haushalte", "haushaltszahl", "haushaltsentwicklung", "haushaltsdaten")),
    "households_non_german": ("Nichtdeutsche Haushalte", ("nichtdeutsche haushalte", "nicht deutsche haushalte")),
    "households_size_1": ("Einpersonenhaushalte", ("einpersonenhaushalte", "1 personen haushalte", "singlehaushalte")),
    "households_size_2": ("Zweipersonenhaushalte", ("zweipersonenhaushalte", "2 personen haushalte")),
    "households_size_3": ("Dreipersonenhaushalte", ("dreipersonenhaushalte", "3 personen haushalte")),
    "households_size_4": ("Vierpersonenhaushalte", ("vierpersonenhaushalte", "4 personen haushalte")),
    "households_size_5_plus": ("Haushalte ab fünf Personen", ("5 personen haushalte", "fünf oder mehr personen", "fuenf oder mehr personen")),
}


class AssistantLLMProvider(Protocol):
    async def plan(self, query: str, context: AssistantContext, tools: list[dict[str, Any]]) -> AssistantPlan: ...


@dataclass(slots=True)
class _PreparedPlan:
    plan: AssistantPlan
    areas: list[SearchArea]
    filters: SearchFilters
    topic: str | None = None
    message: str | None = None
    llm_used: bool = False
    provider_error: str | None = None
    error_code: str | None = None
    metric_key: str | None = None
    choices: list[dict[str, Any]] | None = None


async def answer_assistant_query(
    session: AsyncSession,
    request: AssistantQueryRequest,
    *,
    provider: AssistantLLMProvider | None = None,
) -> AssistantQueryResponse:
    started = time.monotonic()
    prepared = await _plan_query(session, request, provider=provider)
    if len(prepared.plan.steps) > MAX_ASSISTANT_TOOL_CALLS:
        prepared = _unsupported(
            "Die Frage benötigt mehr als vier sichere Datenoperationen.",
            code="ASSISTANT_TOOL_LIMIT_REACHED",
        )

    results: list[tuple[AssistantToolName, Any]] = []
    success = True
    warnings: list[str] = []
    failure_code: str | None = None
    try:
        for step in prepared.plan.steps:
            result = await execute_assistant_tool(session, step.tool, step.arguments)
            results.append((step.tool, result.model_dump(mode="json")))
    except AssistantToolError as error:
        success = False
        warnings.append(error.message)
        failure_code = _assistant_error_code(error.code)

    response = _build_response(request, prepared, results, warnings, failure_code)
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    settings = get_settings()
    response.telemetry = AssistantTelemetry(
        llm_used=prepared.llm_used,
        model=settings.ai_search_model if prepared.llm_used else None,
        tool_calls=len(results),
        duration_ms=duration_ms,
        intent=prepared.plan.intent,
        success=success and prepared.plan.intent != AssistantIntent.UNSUPPORTED,
        provider=(getattr(provider, "name", None) if prepared.llm_used else None),
        prompt_version=ASSISTANT_PROMPT_VERSION,
        knowledge_version=KNOWLEDGE_VERSION,
        tool_registry_version=TOOL_REGISTRY_VERSION,
        input_tokens=getattr(provider, "usage", {}).get("input_tokens"),
        output_tokens=getattr(provider, "usage", {}).get("output_tokens"),
        total_tokens=getattr(provider, "usage", {}).get("total_tokens"),
    )
    log_values = (
        prepared.plan.intent, prepared.llm_used, len(results), duration_ms,
        response.telemetry.success,
    )
    if settings.assistant_query_logging:
        logger.info(
            "assistant_query intent=%s llm_used=%s tool_calls=%d duration_ms=%d "
            "success=%s query=%r",
            *log_values,
            request.query,
        )
    else:
        logger.info(
            "assistant_query intent=%s llm_used=%s tool_calls=%d duration_ms=%d success=%s",
            *log_values,
        )
    return response


async def _plan_query(
    session: AsyncSession,
    request: AssistantQueryRequest,
    *,
    provider: AssistantLLMProvider | None,
) -> _PreparedPlan:
    normalized = normalize_search_text(request.query)
    if _is_forbidden(normalized):
        return _refusal()

    filters = _filters(normalized, request.context.active_filters)
    if request.context.selected_osm_feature and _has(
        normalized, "warum", "kategorie", "gastronomie", "leerstehend", "belegungsstatus"
    ):
        selected = request.context.selected_osm_feature
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[AssistantStep(
                tool=AssistantToolName.GET_OSM_FEATURE_DETAIL,
                arguments=selected.model_dump(mode="json"),
            )]),
            [],
            filters,
            "OSM_EXPLANATION",
        )

    areas = await _mentioned_areas(session, normalized)
    if not areas and request.context.active_area:
        areas = [request.context.active_area]
    duplicate_names = {area.name.casefold() for area in areas if sum(
        candidate.name.casefold() == area.name.casefold() for candidate in areas
    ) > 1}
    if duplicate_names:
        return _clarification(
            "Das genannte Gebiet ist nicht eindeutig. Bitte verwenden Sie den eindeutigen Gebietsslug.",
            areas,
        )

    statistics_plan = _statistics_plan(normalized, areas, filters, request.context)
    if statistics_plan is not None:
        return statistics_plan

    if not areas:
        standalone_knowledge = _knowledge_plan(normalized, [], filters)
        if standalone_knowledge is not None:
            return standalone_knowledge

    knowledge_plan = _knowledge_plan(normalized, areas, filters)
    if knowledge_plan is not None:
        return knowledge_plan

    area_type = _area_type(normalized)
    if area_type and _has(normalized, "alle", "zeige", "anzeigen"):
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.LIST_AREAS, steps=[AssistantStep(
                tool=AssistantToolName.LIST_AREAS, arguments={"area_type": area_type}
            )]), [], filters, "AREA_LIST",
        )

    if _filter_only(normalized):
        return _PreparedPlan(AssistantPlan(intent=AssistantIntent.CHANGE_FILTERS), areas, filters, "FILTER")

    if _has(normalized, "datenquellen", "datenquellenstatus", "importstatus"):
        return _PreparedPlan(AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[AssistantStep(
            tool=AssistantToolName.GET_DATA_SOURCE_STATUS, arguments={}
        )]), [], filters, "DATA_SOURCE_STATUS")

    selected_radius = re.search(r"\bumkreis(?:\s+von)?\s+(\d{2,4})\s*metern?", normalized)
    if selected_radius and request.context.selected_polygon_slug:
        radius = int(selected_radius.group(1))
        if not 100 <= radius <= 2000:
            return _unsupported("Der unterstützte Umkreis liegt zwischen 100 und 2.000 Metern.")
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[AssistantStep(
                tool=AssistantToolName.GET_POLYGON_LOCATION,
                arguments={
                    "slug": request.context.selected_polygon_slug,
                    "radius_m": radius,
                },
            )]),
            areas,
            filters,
            "LOCATION",
        )

    location_match = re.search(r"\bumkreis(?:\s+von)?\s+(\d{2,4})\s*metern?.*\bfl[aä]che\s+([a-z0-9_-]+)", normalized)
    if location_match:
        radius = int(location_match.group(1))
        slug = location_match.group(2)
        if not 100 <= radius <= 2000:
            return _unsupported("Der unterstützte Umkreis liegt zwischen 100 und 2.000 Metern.")
        return _PreparedPlan(AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[
            AssistantStep(tool=AssistantToolName.GET_POLYGON_DETAIL, arguments={"slug": slug}),
            AssistantStep(tool=AssistantToolName.GET_POLYGON_LOCATION, arguments={"slug": slug, "radius_m": radius}),
        ]), [], filters, "LOCATION")

    if _has(normalized, "vergleiche", "vergleich", "mehr leerstände", "mehr leerstaende"):
        comparison_areas = areas or request.context.last_compared_areas
        if len(comparison_areas) < 2:
            return _unsupported("Für einen Vergleich müssen mindestens zwei eindeutige Gebiete genannt werden.")
        if len(comparison_areas) > 3:
            return _unsupported("Für diese Anfrage wären mehr als vier Tool-Aufrufe erforderlich.")
        steps = _resolve_steps(comparison_areas)
        steps.append(AssistantStep(tool=AssistantToolName.COMPARE_AREAS, arguments={
            "area_slugs": [area.slug for area in comparison_areas],
            "include_municipality_benchmark": True,
            "filters": filters.model_dump(),
        }))
        topic = "COMPARISON_MAX_VACANCY" if _has(normalized, "mehr leerstände", "mehr leerstaende") else "COMPARISON"
        return _PreparedPlan(AssistantPlan(intent=AssistantIntent.COMPARE_AREAS, steps=steps), comparison_areas, filters, topic)

    area = areas[0] if areas else None
    if area is None:
        return await _provider_or_unsupported(
            request, provider, filters, [], normalized
        )

    prefix = _resolve_steps([area])
    if _has(normalized, "welche quartiere", "quartiere gehören", "quartiere gehoeren"):
        return _PreparedPlan(AssistantPlan(intent=AssistantIntent.LIST_AREAS, steps=prefix + [AssistantStep(
            tool=AssistantToolName.LIST_AREAS,
            arguments={"area_type": "QUARTER", "parent_slug": area.slug},
        )]), [area], filters, "CHILD_AREAS")

    osm_amenities = _poi_amenities(normalized)
    if osm_amenities:
        poi_filters = SearchFilters(sources=["OSM"])
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.SHOW_FEATURES, steps=prefix + [
                AssistantStep(tool=AssistantToolName.SEARCH_FEATURES, arguments={
                    "area_slug": area.slug,
                    "filters": poi_filters.model_dump(),
                    "geometry_filter": "ALL",
                    "osm_amenities": osm_amenities,
                    "limit": 200,
                }),
            ]),
            [area], poi_filters, "FEATURES",
        )

    topic = _topic(normalized, request.context.last_topic)
    wants_map = _has(normalized, "zeige", "anzeigen", "karte")
    has_feature_constraint = _has_explicit_feature_constraint(normalized)
    if wants_map and not has_feature_constraint and _is_area_map_query(normalized, area):
        step = AssistantStep(
            tool=AssistantToolName.GET_AREA_DETAIL,
            arguments={"slug": area.slug},
        )
        topic = "AREA_DETAIL"
    elif wants_map and has_feature_constraint:
        polygon_features = request.context.last_topic == "POLYGONS" or _has(
            normalized, "fläche", "flächen", "flaeche", "flaechen", "verkaufsflächen", "verkaufsflaechen"
        )
        geometry = "POLYGONS_ONLY" if polygon_features else "ALL"
        step = AssistantStep(tool=AssistantToolName.SEARCH_FEATURES, arguments={
            "area_slug": area.slug, "filters": filters.model_dump(),
            "geometry_filter": geometry, "limit": 200,
        })
        topic = "POLYGON_FEATURES" if polygon_features else "FEATURES"
    elif _has(normalized, "welche verkaufsflächen", "welche verkaufsflaechen"):
        step = AssistantStep(tool=AssistantToolName.LIST_AREA_POLYGONS, arguments={
            "slug": area.slug, "filters": filters.model_dump(), "limit": 24,
        })
        topic = "POLYGONS"
    elif topic == "AREA_SIZE":
        step = AssistantStep(tool=AssistantToolName.GET_AREA_DETAIL, arguments={"slug": area.slug})
    elif topic == "STATISTICS":
        step = AssistantStep(tool=AssistantToolName.GET_AREA_STATISTICS, arguments={"slug": area.slug})
    elif topic in {"POI_COUNT", "POI_TYPES", "VACANCY", "GASTRONOMY_COUNT", "ANALYTICS"}:
        step = AssistantStep(tool=AssistantToolName.GET_AREA_ANALYTICS, arguments={
            "slug": area.slug, "filters": filters.model_dump(),
        })
    elif _is_area_detail_query(normalized, area):
        step = AssistantStep(tool=AssistantToolName.GET_AREA_DETAIL, arguments={"slug": area.slug})
        topic = "AREA_DETAIL"
    else:
        return await _provider_or_unsupported(
            request, provider, filters, [area], normalized
        )
    intent = AssistantIntent.SHOW_FEATURES if topic in {"FEATURES", "POLYGON_FEATURES"} else AssistantIntent.ANSWER_QUESTION
    return _PreparedPlan(AssistantPlan(intent=intent, steps=prefix + [step]), [area], filters, topic)


def _statistics_plan(
    normalized: str,
    areas: list[SearchArea],
    filters: SearchFilters,
    context: AssistantContext,
) -> _PreparedPlan | None:
    metric_keys = _statistic_metric_keys(normalized)
    continuation = normalized.startswith(("und ", "wie hat", "zeig die", "zeige die"))
    wants_series = _has(
        normalized, "entwicklung", "zeitreihe", "zeitverlauf", "verlauf",
        "wie hat sich", "über die jahre", "ueber die jahre",
    )
    wants_overview = _has(
        normalized, "welche statistiken", "welche statistik", "statistikübersicht",
        "statistikuebersicht", "kommunale kennzahlen", "welche daten gibt es",
    )
    wants_explanation = _has(
        normalized, "quelle", "datengrundlage", "dokumentation", "woher",
        "erkläre", "erklaere", "was bedeutet",
    )
    wants_metric_explanation = bool(context.last_metric_key) and wants_explanation and _has(
        normalized, "kennzahl", "diese kennzahl", "was bedeutet sie",
    )
    statistic_signal = bool(metric_keys) or wants_overview or _has(
        normalized, "kommunale statistik", "bevölkerungsstatistik", "bevoelkerungsstatistik"
    ) or wants_metric_explanation or (continuation and context.last_topic in {
        "STATISTICS_OVERVIEW", "STATISTIC_METRIC", "STATISTIC_SERIES",
        "STATISTICS_OVERVIEW_KNOWLEDGE", "STATISTIC_METRIC_KNOWLEDGE",
        "STATISTIC_SERIES_KNOWLEDGE",
    })
    if not statistic_signal:
        return None
    if not areas:
        return None

    area = areas[0]
    if wants_metric_explanation:
        metric_key = context.last_metric_key
        knowledge_key = (
            f"statistic.{metric_key}"
            if metric_key in {"population", "households"}
            else "data_source.STATISTICS"
        )
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[AssistantStep(
                tool=AssistantToolName.GET_CONCEPT,
                arguments={"key": knowledge_key},
            )]),
            [area], filters, "STATISTIC_EXPLANATION", metric_key=metric_key,
        )
    if wants_series and not metric_keys and context.last_metric_key:
        metric_keys = [context.last_metric_key]
    if len(metric_keys) > 1:
        choices = [
            {"key": key, "name": STATISTIC_METRICS[key][0], "value": key}
            for key in metric_keys
        ]
        return _metric_clarification(
            "Mehrere Kennzahlen passen zur Frage. Bitte wählen Sie eine Kennzahl aus.",
            [area], filters, choices,
        )

    steps = _resolve_steps([area])
    metric_key = metric_keys[0] if metric_keys else None
    if wants_series:
        if metric_key is None:
            return _metric_clarification(
                "Für welche Kennzahl soll die Zeitreihe angezeigt werden?",
                [area], filters,
                [
                    {"key": key, "name": title, "value": key}
                    for key, (title, _) in list(STATISTIC_METRICS.items())[:6]
                ],
            )
        steps.append(AssistantStep(
            tool=AssistantToolName.GET_STATISTIC_SERIES,
            arguments={"slug": area.slug, "metric_key": metric_key},
        ))
        topic = "STATISTIC_SERIES"
    else:
        steps.append(AssistantStep(
            tool=AssistantToolName.GET_AREA_STATISTICS,
            arguments={"slug": area.slug},
        ))
        topic = "STATISTIC_METRIC" if metric_key else "STATISTICS_OVERVIEW"

    if wants_explanation:
        knowledge_key = (
            f"statistic.{metric_key}"
            if metric_key in {"population", "households"}
            else "data_source.STATISTICS"
        )
        steps.append(AssistantStep(
            tool=AssistantToolName.GET_CONCEPT,
            arguments={"key": knowledge_key},
        ))
        topic += "_KNOWLEDGE"
    return _PreparedPlan(
        AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=steps),
        [area], filters, topic, metric_key=metric_key,
    )


def _statistic_metric_keys(normalized: str) -> list[str]:
    matches = [
        key for key, (_, aliases) in STATISTIC_METRICS.items()
        if _has(normalized, *aliases)
    ]
    if "population_non_german" in matches and "population" in matches:
        matches.remove("population")
    if "households_non_german" in matches and "households" in matches:
        matches.remove("households")
    if any(key.startswith("households_size_") for key in matches) and "households" in matches:
        matches.remove("households")
    return matches


async def _provider_or_unsupported(
    request: AssistantQueryRequest,
    provider: AssistantLLMProvider | None,
    filters: SearchFilters,
    areas: list[SearchArea],
    normalized: str,
) -> _PreparedPlan:
    if _out_of_scope(normalized):
        return _unsupported(
            "Ich kann Fragen zu den Daten und Funktionen des Stadtplaners beantworten."
        )
    if provider is None:
        return _unsupported(
            "Die erweiterte Sprachinterpretation ist nicht aktiviert. Diese Objekt- "
            "oder Fachfrage kann deshalb nicht zuverlässig geplant werden.",
            code="ASSISTANT_DISABLED",
        )

    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_model.model_json_schema(),
        }
        for tool in ASSISTANT_TOOL_REGISTRY.values()
    ]
    provider_context = request.context.model_copy(deep=True)
    if areas:
        provider_context.active_area = areas[0]
    try:
        plan = AssistantPlan.model_validate(
            await provider.plan(request.query, provider_context, tools)
        )
        return _PreparedPlan(
            plan, areas, filters, _provider_topic(plan), llm_used=True
        )
    except AssistantProviderError as error:
        fallback = _unsupported(
            "Die intelligente Sprachinterpretation ist derzeit nicht verfügbar. "
            "Einfache Stadtplaner-Suchen funktionieren weiterhin."
        )
        fallback.llm_used = True
        fallback.provider_error = error.code
        fallback.error_code = error.code
        return fallback
    except (ValidationError, ValueError):
        fallback = _unsupported(
            "Die Sprachinterpretation lieferte keinen gültigen sicheren Plan.",
            code="ASSISTANT_INVALID_PLAN",
        )
        fallback.llm_used = True
        return fallback


def _build_response(
    request: AssistantQueryRequest,
    prepared: _PreparedPlan,
    results: list[tuple[AssistantToolName, Any]],
    warnings: list[str],
    failure_code: str | None,
) -> AssistantQueryResponse:
    if prepared.plan.response_mode == AssistantResponseMode.REFUSAL:
        answer = "Diese Anfrage ist nicht erlaubt. Der Assistent kann ausschließlich öffentliche Stadtplaner-Daten lesen."
        presentation = AnswerPresentation(type=AnswerPresentationType.TEXT, title="Nicht erlaubte Anfrage", value=answer)
    elif prepared.plan.response_mode == AssistantResponseMode.CLARIFICATION:
        answer = prepared.message or "Bitte präzisieren Sie das gewünschte Gebiet."
        presentation = AnswerPresentation(
            type=AnswerPresentationType.AREA_LIST,
            title=("Kennzahl präzisieren" if prepared.choices else "Gebiet präzisieren"),
            value=None,
            items=(prepared.choices or [
                area.model_dump(mode="json") for area in prepared.areas
            ]),
        )
    elif prepared.plan.intent == AssistantIntent.UNSUPPORTED:
        answer = prepared.message or "Diese Frage kann mit den verfügbaren Stadtplaner-Daten derzeit nicht zuverlässig beantwortet werden."
        presentation = AnswerPresentation(type=AnswerPresentationType.TEXT, title="Nicht unterstützt", value=answer)
    elif warnings:
        answer = warnings[0]
        presentation = AnswerPresentation(type=AnswerPresentationType.TEXT, title="Keine belastbare Antwort", value=answer)
    else:
        answer, presentation = _answer_from_results(prepared, results)

    citations, sources = _sources(prepared, results)
    actions = _map_actions(request.query, prepared, results)
    context = request.context.model_copy(deep=True)
    if prepared.areas and prepared.plan.response_mode != AssistantResponseMode.CLARIFICATION:
        context.active_area = prepared.areas[0]
    context.active_filters = prepared.filters
    context.last_intent = prepared.plan.intent
    context.last_topic = (
        prepared.topic if prepared.plan.intent != AssistantIntent.UNSUPPORTED else None
    )
    if prepared.metric_key:
        context.last_metric_key = prepared.metric_key
    if sources:
        context.last_source_type = sources[-1].type
    if prepared.plan.intent == AssistantIntent.COMPARE_AREAS:
        context.last_compared_areas = prepared.areas
    return AssistantQueryResponse(
        query=request.query, answer=answer, plan=prepared.plan, presentation=presentation,
        citations=citations, sources_used=sources, map_actions=actions, context=context,
        warnings=[*warnings, *([prepared.provider_error] if prepared.provider_error else [])],
        error_code=failure_code or prepared.error_code,
        claims=_claims(answer, prepared, results),
        follow_up_actions=_follow_up_actions(prepared),
        presentation_behavior=_presentation_behavior(prepared),
        telemetry=AssistantTelemetry(tool_calls=0, duration_ms=0, intent=prepared.plan.intent, success=False),
    )


def _answer_from_results(prepared: _PreparedPlan, results: list[tuple[AssistantToolName, Any]]) -> tuple[str, AnswerPresentation]:
    useful = results[-1][1] if results else {}
    data = useful.get("data", useful)
    area_name = prepared.areas[0].name if prepared.areas else "dem Gebiet"
    topic = prepared.topic
    if topic in {"KNOWLEDGE", "DATASETS"}:
        items = useful.get("items", []) if isinstance(useful, dict) else []
        if not items:
            return (
                "Zu diesem Begriff liegt kein kontrollierter Wissenseintrag vor.",
                AnswerPresentation(type=AnswerPresentationType.KNOWLEDGE, title="Nicht gefunden"),
            )
        title = items[0].get("title", "Stadtplaner-Wissen") if len(items) == 1 else "Stadtplaner-Wissen"
        answer = " ".join(str(item.get("description", "")) for item in items if item.get("description"))
        return answer, AnswerPresentation(
            type=AnswerPresentationType.KNOWLEDGE, title=title, items=items
        )
    if topic == "STATISTIC_EXPLANATION":
        items = useful.get("items", []) if isinstance(useful, dict) else []
        if not items:
            answer = "Zu dieser Kennzahl liegt derzeit keine kontrollierte Dokumentation vor."
            return answer, AnswerPresentation(
                type=AnswerPresentationType.KNOWLEDGE,
                title="Kennzahl nicht dokumentiert",
            )
        answer = " ".join(
            str(item.get("description", "")) for item in items if item.get("description")
        )
        return answer, AnswerPresentation(
            type=AnswerPresentationType.KNOWLEDGE,
            title=str(items[0].get("title") or "Kennzahl erklärt"),
            items=items,
        )
    if topic and topic.startswith("STATISTIC"):
        statistic_result = _tool_result_data(results, {
            AssistantToolName.GET_AREA_STATISTICS,
            AssistantToolName.GET_STATISTIC_SERIES,
        })
        statistic_data = statistic_result.get("data", {}) if isinstance(statistic_result, dict) else {}
        knowledge = _tool_result_data(results, {AssistantToolName.GET_CONCEPT})
        knowledge_items = knowledge.get("items", []) if isinstance(knowledge, dict) else []
        sections = ([AnswerPresentationSection(
            type=AnswerPresentationType.KNOWLEDGE,
            title="Definition und Datengrundlage",
            items=knowledge_items,
        )] if knowledge_items else [])
        metadata = _statistics_metadata(statistic_data)
        if topic.startswith("STATISTIC_SERIES"):
            metric = statistic_data.get("metric") or {}
            items = statistic_data.get("series") or []
            title = str(metric.get("name") or STATISTIC_METRICS.get(
                prepared.metric_key or "", ("Statistische Kennzahl", ())
            )[0])
            answer = _statistics_answer_prefix(statistic_data) + (
                f"Die Zeitreihe {title} für {area_name} enthält {len(items)} Berichtsperioden."
            )
            return answer, AnswerPresentation(
                type=AnswerPresentationType.STATISTIC_SERIES,
                title=f"{title} in {area_name}", unit=metric.get("unit"),
                items=items, metadata=metadata, sections=sections,
            )
        latest = statistic_data.get("latest") or []
        if topic.startswith("STATISTIC_METRIC"):
            item = next((row for row in latest if row.get("key") == prepared.metric_key), None)
            title = STATISTIC_METRICS.get(
                prepared.metric_key or "", ("Statistische Kennzahl", ())
            )[0]
            if item is None:
                answer = f"Für die Kennzahl {title} liegt in {area_name} kein veröffentlichter Wert vor."
                return answer, AnswerPresentation(
                    type=AnswerPresentationType.STATISTIC_METRIC,
                    title=f"{title} in {area_name}", metadata=metadata,
                    sections=sections,
                )
            answer = _statistics_answer_prefix(statistic_data) + (
                f"{item.get('name') or title} beträgt {item.get('value')} "
                f"{_unit_label(item.get('unit'))} für die Periode {item.get('period')}."
            ).strip()
            return answer, AnswerPresentation(
                type=AnswerPresentationType.STATISTIC_METRIC,
                title=f"{item.get('name') or title} in {area_name}",
                value=item.get("value"), unit=item.get("unit"), items=[item],
                metadata=metadata, sections=sections,
            )
        answer = _statistics_answer_prefix(statistic_data) + (
            f"Für {area_name} liegen {len(latest)} kommunale Kennzahlen vor."
        )
        return answer, AnswerPresentation(
            type=AnswerPresentationType.STATISTICS_OVERVIEW,
            title=f"Statistik für {area_name}", items=latest,
            metadata=metadata, sections=sections,
        )
    if topic in {"COMBINED_GASTRONOMY", "COMBINED_VACANCY", "MAP_KNOWLEDGE", "COMPARISON_KNOWLEDGE"}:
        knowledge = _tool_result_data(results, {
            AssistantToolName.DESCRIBE_CATEGORY,
            AssistantToolName.DESCRIBE_METRIC,
            AssistantToolName.GET_CONCEPT,
            AssistantToolName.SEARCH_KNOWLEDGE,
        })
        knowledge_items = knowledge.get("items", []) if isinstance(knowledge, dict) else []
        explanation = str(knowledge_items[0].get("description", "")) if knowledge_items else ""
        knowledge_sections = ([AnswerPresentationSection(
            type=AnswerPresentationType.KNOWLEDGE,
            title="Definition und Datengrundlage",
            items=knowledge_items,
        )] if knowledge_items else [])
        if topic == "COMPARISON_KNOWLEDGE":
            comparison = _tool_result_data(results, {AssistantToolName.COMPARE_AREAS})
            items = comparison.get("data", {}).get("areas", []) if isinstance(comparison, dict) else []
            answer = "Ich habe die Gebiete anhand der erfassten Flächenkennzahlen verglichen."
            if explanation:
                answer += f" {explanation}"
            return answer, AnswerPresentation(
                type=AnswerPresentationType.COMPARISON, title="Gebietsvergleich",
                items=items, sections=knowledge_sections,
            )
        analytics = _tool_result_data(results, {AssistantToolName.GET_AREA_ANALYTICS})
        analytics_data = analytics.get("data", {}) if isinstance(analytics, dict) else {}
        if topic == "COMBINED_GASTRONOMY":
            value = analytics_data.get("metrics", {}).get("polygon_count")
            lead = (
                f"Für {area_name} sind {value} Gastronomieflächen erfasst."
                if value is not None else "Für diese Auswahl liegt keine belastbare Zahl vor."
            )
            return f"{lead} {explanation}".strip(), AnswerPresentation(
                type=AnswerPresentationType.METRIC, title=f"Gastronomieflächen in {area_name}",
                value=value, items=knowledge_items, sections=knowledge_sections,
            )
        if topic == "COMBINED_VACANCY":
            value = analytics_data.get("metrics", {}).get("vacancy_rate")
            lead = (
                f"Die berechnete Leerstandsquote in {area_name} beträgt {value} %."
                if value is not None else "Für diese Auswahl liegt keine belastbare Leerstandsquote vor."
            )
            return f"{lead} {explanation}".strip(), AnswerPresentation(
                type=AnswerPresentationType.METRIC, title=f"Leerstandsquote in {area_name}",
                value=value, unit="%", items=knowledge_items, sections=knowledge_sections,
            )
        feature_result = _tool_result_data(results, {AssistantToolName.SEARCH_FEATURES})
        feature_data = feature_result.get("data", {}) if isinstance(feature_result, dict) else {}
        features = feature_data.get("feature_collection", {}).get("features", [])
        answer = f"Ich zeige {len(features)} passende Objekte in {area_name}. {explanation}".strip()
        return answer, AnswerPresentation(
            type=AnswerPresentationType.FEATURE_LIST, title=f"Objekte in {area_name}",
            value=len(features), items=[item.get("properties", {}) for item in features[:20]],
            sections=knowledge_sections,
        )
    if topic == "OSM_EXPLANATION":
        category = data.get("category_explanation") if isinstance(data, dict) else None
        occupancy = data.get("occupancy_explanation") if isinstance(data, dict) else None
        answer = " ".join(value for value in (category, occupancy) if value)
        return answer, AnswerPresentation(
            type=AnswerPresentationType.KNOWLEDGE,
            title=str(data.get("name") or "OSM-Erklärung"),
            items=[data] if isinstance(data, dict) else [],
        )
    if topic == "AREA_LIST":
        items = useful.get("items", [])
        answer = f"Es wurden {len(items)} Gebiete gefunden."
        return answer, AnswerPresentation(type=AnswerPresentationType.AREA_LIST, title="Gebiete", items=items)
    if topic == "CHILD_AREAS":
        items = useful.get("items", [])
        answer = f"Zu {area_name} gehören {len(items)} erfasste Quartiere."
        return answer, AnswerPresentation(type=AnswerPresentationType.AREA_LIST, title=f"Quartiere in {area_name}", items=items)
    if topic == "AREA_SIZE":
        value = data.get("area_m2") if isinstance(data, dict) else None
        if value is None:
            return _missing_metric(f"Fläche von {area_name}")
        area_km2 = f"{float(value) / 1_000_000:.2f}".replace(".", ",")
        answer = f"{area_name} ist {area_km2} km² groß."
        return answer, AnswerPresentation(type=AnswerPresentationType.METRIC, title=f"Fläche von {area_name}", value=value, unit="m²")
    if topic == "POI_COUNT":
        value = data.get("poi_count") if isinstance(data, dict) else None
        return _metric_answer(value, f"POIs in {area_name}", f"Für {area_name} sind {{value}} POIs erfasst.")
    if topic == "GASTRONOMY_COUNT":
        value = data.get("metrics", {}).get("polygon_count") if isinstance(data, dict) else None
        return _metric_answer(value, f"Gastronomieflächen in {area_name}", f"Für {area_name} sind {{value}} Gastronomieflächen im Stadtplaner erfasst.")
    if topic == "VACANCY":
        value = data.get("metrics", {}).get("vacancy_rate") if isinstance(data, dict) else None
        if value is None:
            return _missing_metric(f"Leerstandsquote in {area_name}")
        answer = f"Die berechnete Leerstandsquote in {area_name} beträgt {value} %."
        return answer, AnswerPresentation(type=AnswerPresentationType.METRIC, title=f"Leerstandsquote in {area_name}", value=value, unit="%")
    if topic == "POI_TYPES":
        items = data.get("poi_categories", []) if isinstance(data, dict) else []
        answer = f"Für {area_name} sind {len(items)} POI-Arten erfasst."
        return answer, AnswerPresentation(type=AnswerPresentationType.METRIC_LIST, title=f"POI-Arten in {area_name}", items=items)
    if topic in {"COMPARISON", "COMPARISON_MAX_VACANCY"}:
        items = data.get("areas", []) if isinstance(data, dict) else []
        if topic == "COMPARISON_MAX_VACANCY" and items:
            known = [item for item in items if isinstance(item.get("metrics", {}).get("vacant_count"), int)]
            if not known:
                return _missing_metric("Leerstände im Vergleich")
            maximum = max(known, key=lambda item: item["metrics"]["vacant_count"])
            value = maximum["metrics"]["vacant_count"]
            answer = f"{maximum.get('name', 'Das Gebiet')} hat mit {value} erfassten Leerständen den höheren Wert."
            return answer, AnswerPresentation(type=AnswerPresentationType.METRIC, title="Mehr Leerstände", value=value, unit=None, items=items)
        answer = "Ich habe " + " und ".join(item.get("name", "Gebiet") for item in items) + " anhand der erfassten Flächenkennzahlen verglichen."
        return answer, AnswerPresentation(type=AnswerPresentationType.COMPARISON, title="Gebietsvergleich", items=items)
    if topic == "STATISTICS":
        items = data.get("latest", []) if isinstance(data, dict) else []
        inherited = bool(data.get("inherited_from_parent")) if isinstance(data, dict) else False
        prefix = "Die Werte stammen derzeit vom übergeordneten Gebiet. " if inherited else ""
        answer = prefix + f"Für {area_name} liegen {len(items)} kommunale Kennzahlen vor."
        return answer, AnswerPresentation(type=AnswerPresentationType.METRIC_LIST, title=f"Statistik für {area_name}", items=items)
    if topic in {"FEATURES", "POLYGON_FEATURES"}:
        collection = data.get("feature_collection", {}) if isinstance(data, dict) else {}
        features = collection.get("features", []) if isinstance(collection, dict) else []
        count = len(features)
        answer = (
            f"Ich zeige ein passendes Objekt in {area_name}."
            if count == 1 else f"Ich zeige {count} passende Objekte in {area_name}."
        )
        items = [feature.get("properties", {}) for feature in features[:20]]
        return answer, AnswerPresentation(type=AnswerPresentationType.FEATURE_LIST, title=f"Objekte in {area_name}", value=len(features), items=items)
    if topic == "POLYGONS":
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            collection = data.get("feature_collection", {})
            items = [feature.get("properties", {}) for feature in collection.get("features", [])]
        else:
            items = []
        answer = f"Für {area_name} wurden {len(items)} Verkaufsflächen gefunden."
        return answer, AnswerPresentation(type=AnswerPresentationType.FEATURE_LIST, title=f"Verkaufsflächen in {area_name}", value=len(items), items=items)
    if topic == "LOCATION":
        items = data.get("poi_counts", []) if isinstance(data, dict) else []
        total = sum(item.get("count", 0) for item in items if isinstance(item.get("count"), int))
        answer = f"Im gewählten Umkreis sind {total} POIs in {len(items)} Kategorien erfasst."
        return answer, AnswerPresentation(type=AnswerPresentationType.METRIC_LIST, title="POIs im Umkreis", value=total, items=items)
    if topic == "DATA_SOURCE_STATUS":
        items = data if isinstance(data, list) else []
        answer = f"Es liegen Statusinformationen für {len(items)} öffentliche Datenquellen vor."
        return answer, AnswerPresentation(type=AnswerPresentationType.DATA_SOURCE_STATUS, title="Datenquellenstatus", items=items)
    if isinstance(data, dict) and data.get("name"):
        answer = f"Ich zeige die öffentlichen Informationen zu {data['name']}."
        return answer, AnswerPresentation(type=AnswerPresentationType.TEXT, title=data["name"], value=answer)
    return _missing_metric("Ergebnis")


def _metric_answer(value: Any, title: str, template: str) -> tuple[str, AnswerPresentation]:
    if value is None:
        return _missing_metric(title)
    return template.format(value=value), AnswerPresentation(type=AnswerPresentationType.METRIC, title=title, value=value)


def _missing_metric(title: str) -> tuple[str, AnswerPresentation]:
    answer = "Für diese Auswahl liegt keine belastbare Zahl vor."
    return answer, AnswerPresentation(type=AnswerPresentationType.METRIC, title=title, value=None)


def _statistics_metadata(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get("series") or data.get("latest") or []
    period = next((row.get("period") for row in reversed(rows) if row.get("period")), None)
    return {
        "requested_area": data.get("area"),
        "statistics_area": data.get("statistics_area"),
        "inherited_from_parent": bool(data.get("inherited_from_parent")),
        "source": data.get("source"),
        "period": period,
    }


def _statistics_answer_prefix(data: dict[str, Any]) -> str:
    if not data.get("inherited_from_parent"):
        return ""
    statistics_area = data.get("statistics_area") or {}
    name = statistics_area.get("name") or "dem übergeordneten Gebiet"
    return f"Für dieses Gebiet werden die veröffentlichten Werte vom übergeordneten Gebiet {name} verwendet. "


def _unit_label(unit: Any) -> str:
    return {
        "persons": "Personen",
        "households": "Haushalte",
        "percent": "%",
    }.get(str(unit), str(unit or ""))


def _tool_result_data(
    results: list[tuple[AssistantToolName, Any]], names: set[AssistantToolName]
) -> dict[str, Any]:
    return next((result for tool, result in reversed(results) if tool in names), {})


def _sources(prepared: _PreparedPlan, results: list[tuple[AssistantToolName, Any]]) -> tuple[list[AssistantCitation], list[AssistantSource]]:
    citations: list[AssistantCitation] = []
    sources: list[AssistantSource] = []
    for area in prepared.areas:
        citations.append(AssistantCitation(type="area", slug=area.slug))
    for tool, result in results:
        data = result.get("data", result)
        if tool == AssistantToolName.GET_AREA_ANALYTICS:
            slug = prepared.areas[0].slug if prepared.areas else None
            sources.append(AssistantSource(type="ANALYSIS_AREA_ANALYTICS", area_slug=slug))
            citations.append(AssistantCitation(type="analytics", slug=slug))
        elif tool in {AssistantToolName.GET_AREA_STATISTICS, AssistantToolName.GET_STATISTIC_SERIES} and isinstance(data, dict):
            source = data.get("source") or {}
            rows = data.get("series") or data.get("latest") or []
            period = next((item.get("period") for item in reversed(rows) if item.get("period")), None)
            inherited = bool(data.get("inherited_from_parent"))
            slug = prepared.areas[0].slug if prepared.areas else None
            source_type = (
                "STATISTIC_SERIES"
                if tool == AssistantToolName.GET_STATISTIC_SERIES
                else "STATISTICS"
            )
            sources.append(AssistantSource(type=source_type, area_slug=slug, source=source.get("name"), period=period, inherited_from_parent=inherited))
            citations.append(AssistantCitation(type="statistics", slug=slug, source=source.get("name"), period=period, inherited_from_parent=inherited))
        elif tool in {AssistantToolName.SEARCH_FEATURES, AssistantToolName.GET_POLYGON_LOCATION}:
            selected_sources = prepared.filters.sources
            source_type = (
                selected_sources[0]
                if len(selected_sources) == 1
                else "OSM_AND_STADTPLANER"
            )
            sources.append(AssistantSource(
                type=source_type,
                area_slug=prepared.areas[0].slug if prepared.areas else None,
            ))
        elif tool == AssistantToolName.COMPARE_AREAS:
            sources.append(AssistantSource(type="AREA_COMPARISON"))
        elif tool in {
            AssistantToolName.SEARCH_KNOWLEDGE, AssistantToolName.GET_CONCEPT,
            AssistantToolName.DESCRIBE_CATEGORY, AssistantToolName.DESCRIBE_METRIC,
            AssistantToolName.DESCRIBE_FILTER, AssistantToolName.LIST_KNOWN_DATASETS,
        }:
            items = result.get("items", [])
            for item in items:
                source = item.get("source") or {}
                sources.append(AssistantSource(
                    type=("DOCUMENTATION" if source.get("type") == "DOCUMENTATION" else "KNOWLEDGE"),
                    source=source.get("path"),
                    knowledge_key=item.get("key"),
                ))
        elif tool == AssistantToolName.GET_OSM_FEATURE_DETAIL:
            sources.append(AssistantSource(type="OSM"))
    return citations, sources


def _map_actions(query: str, prepared: _PreparedPlan, results: list[tuple[AssistantToolName, Any]]) -> list[AssistantMapAction]:
    normalized = normalize_search_text(query)
    if prepared.plan.intent == AssistantIntent.CHANGE_FILTERS:
        return [AssistantMapAction(type=AssistantMapActionType.UPDATE_FILTERS, filters=prepared.filters)]
    if prepared.topic == "AREA_LIST":
        area_type = _area_type(normalized)
        return [AssistantMapAction(type=AssistantMapActionType.SHOW_ANALYSIS_AREAS, area_type=SearchAreaType(area_type), fit_bounds=True)] if area_type else []
    if prepared.topic in {"FEATURES", "POLYGON_FEATURES", "MAP_KNOWLEDGE"} and results:
        feature_result = _tool_result_data(results, {AssistantToolName.SEARCH_FEATURES})
        data = feature_result.get("data")
        slug = prepared.areas[0].slug
        collection = data.get("feature_collection") if isinstance(data, dict) else None
        bounds = data.get("bounds") if isinstance(data, dict) else None
        return [
            AssistantMapAction(type=AssistantMapActionType.FIT_AREA, area_slug=slug, fit_bounds=True, bounds=bounds),
            AssistantMapAction(
                type=AssistantMapActionType.REPLACE_SEARCH_LAYER, area_slug=slug,
                feature_collection=collection, fit_bounds=True, bounds=bounds,
                filters=prepared.filters,
                geometry_filter=(SearchGeometryFilter.POLYGONS_ONLY if prepared.topic in {"POLYGON_FEATURES", "MAP_KNOWLEDGE"} else SearchGeometryFilter.ALL),
            ),
        ]
    if prepared.plan.intent == AssistantIntent.COMPARE_AREAS and _has(normalized, "zeige", "anzeigen", "karte"):
        if "danach" in normalized:
            tail = normalized.split("danach", 1)[1]
            selected = next((area for area in prepared.areas if _has(tail, area.name, area.slug)), prepared.areas[0])
            return [AssistantMapAction(type=AssistantMapActionType.FIT_AREA, area_slug=selected.slug, fit_bounds=True)]
        return [AssistantMapAction(type=AssistantMapActionType.HIGHLIGHT_AREAS, area_slugs=[area.slug for area in prepared.areas], fit_bounds=True)]
    if prepared.areas and _has(normalized, "zeige", "anzeigen", "karte"):
        data = results[-1][1].get("data", {}) if results else {}
        bounds = data.get("bbox") if isinstance(data, dict) else None
        return [AssistantMapAction(type=AssistantMapActionType.FIT_AREA, area_slug=prepared.areas[0].slug, fit_bounds=True, bounds=bounds)]
    return []


async def _mentioned_areas(session: AsyncSession, normalized: str) -> list[SearchArea]:
    rows = await list_areas(session)
    matches = []
    for row in rows:
        names = (normalize_search_text(row.name), normalize_search_text(row.slug))
        if any(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", normalized) for name in names):
            matches.append(SearchArea(id=row.id, slug=row.slug, name=row.name, area_type=SearchAreaType(row.area_type)))
    unique: dict[str, SearchArea] = {item.id: item for item in matches}
    return list(unique.values())


def _resolve_steps(areas: list[SearchArea]) -> list[AssistantStep]:
    return [AssistantStep(tool=AssistantToolName.RESOLVE_AREA, arguments={"name_or_slug": area.slug}) for area in areas]


def _filters(normalized: str, active: SearchFilters) -> SearchFilters:
    explicit_source: str | None = None
    if _has(normalized, "stadtplaner"):
        explicit_source = "STADTPLANNER"
    elif _has(normalized, "osm", "openstreetmap"):
        explicit_source = "OSM"

    values = (
        active.model_copy(deep=True)
        if _inherits_active_filters(normalized)
        else SearchFilters()
    )
    if explicit_source:
        values.sources = [explicit_source]
    for category, synonyms in SEARCH_CATALOG.category_synonyms.items():
        if _has(normalized, *synonyms):
            values.categories = [category]
            break
    if _has(normalized, *VACANCY_SYNONYMS):
        values.occupancy_statuses = ["VACANT"]
    elif _has(normalized, "belegt", "vermietet"):
        values.occupancy_statuses = ["OCCUPIED"]
    if _has(normalized, "erdgeschoss", "eg"):
        values.floors = ["EG"]
    return values


def _inherits_active_filters(normalized: str) -> bool:
    """Übernimmt die aktuelle Auswahl nur bei einem erkennbaren Folgebefehl."""
    return (
        _filter_only(normalized)
        or normalized.startswith(("und ", "davon ", "dort ", "jetzt "))
        or _has(
            normalized,
            "davon", "weiterhin", "zusätzlich", "zusaetzlich",
        )
    )


def _topic(normalized: str, previous: str | None) -> str:
    if _has(normalized, "wie groß", "wie gross", "fläche des gebiets", "flaeche des gebiets"):
        return "AREA_SIZE"
    if _has(normalized, "welche arten von pois", "poi arten", "poi-arten"):
        return "POI_TYPES"
    if _has(normalized, "wie viele pois", "anzahl pois"):
        return "POI_COUNT"
    if _has(normalized, "gastronomie") and _has(normalized, "wie viele", "anzahl"):
        return "GASTRONOMY_COUNT"
    if _has(normalized, "wie viele flächen", "wie viele flaechen", "anzahl flächen", "anzahl flaechen"):
        return "ANALYTICS"
    if _has(normalized, "leerstandsquote", "wie hoch ist der leerstand", "wie hoch ist die leerstandsquote"):
        return "VACANCY"
    if _has(normalized, "einwohner", "bevölkerung", "bevoelkerung", "bevölkerungsstatistik", "bevoelkerungsstatistik", "statistik", "kennzahl"):
        return "STATISTICS"
    if normalized.startswith("und ") and previous:
        return previous
    return ""


def _area_type(normalized: str) -> str | None:
    if _has(normalized, "stadtteile", "stadtteil"):
        return "DISTRICT"
    if _has(normalized, "quartiere", "quartier"):
        return "QUARTER"
    if _has(normalized, "gemeinden", "gemeinde"):
        return "MUNICIPALITY"
    return None


def _has(normalized: str, *values: str) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(normalize_search_text(value))}(?!\w)", normalized) for value in values)


def _filter_only(normalized: str) -> bool:
    return normalized.startswith("nur ") and _has(normalized, "leerstand", "leerstände", "leerstaende", "belegt", "erdgeschoss")


def _poi_amenities(normalized: str) -> list[str]:
    return [
        amenity
        for amenity, synonyms in POI_AMENITY_SYNONYMS.items()
        if _has(normalized, *synonyms)
    ]


def _is_area_detail_query(normalized: str, area: SearchArea) -> bool:
    return normalized in {
        normalize_search_text(area.name), normalize_search_text(area.slug)
    } or _has(
        normalized,
        "informationen", "information", "details", "gebietsdetails",
    )


def _is_area_map_query(normalized: str, area: SearchArea) -> bool:
    if _has(normalized, "karte"):
        return True
    name = normalize_search_text(area.name)
    slug = normalize_search_text(area.slug)
    return normalized in {
        f"zeige {name}", f"bitte {name} anzeigen", f"{name} anzeigen",
        f"zeige {slug}", f"bitte {slug} anzeigen", f"{slug} anzeigen",
    }


def _has_explicit_feature_constraint(normalized: str) -> bool:
    category_terms = tuple(
        term
        for synonyms in SEARCH_CATALOG.category_synonyms.values()
        for term in synonyms
    )
    return _has(
        normalized,
        *category_terms,
        *VACANCY_SYNONYMS,
        "belegt", "vermietet", "poi", "pois", "objekt", "objekte",
        "fläche", "flächen", "flaeche", "flaechen",
        "verkaufsfläche", "verkaufsflächen", "verkaufsflaeche",
        "verkaufsflaechen",
    )


def _knowledge_plan(
    normalized: str, areas: list[SearchArea], filters: SearchFilters
) -> _PreparedPlan | None:
    asks_explanation = _has(
        normalized, "was bedeutet", "was ist", "was zählt", "was zaehlt",
        "erkläre", "erklaere", "wie erkennt", "warum ist", "unterschied",
        "quelle", "datengrundlage", "dokumentation", "woher",
    )
    if _has(normalized, "welche datenquellen", "welche datensätze", "welche datensaetze"):
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[AssistantStep(
                tool=AssistantToolName.LIST_KNOWN_DATASETS, arguments={}
            )]), [], filters, "DATASETS",
        )

    if areas and _has(normalized, "vergleich", "vergleiche") and asks_explanation:
        if len(areas) != 2:
            return None
        steps = _resolve_steps(areas)
        steps.extend([
            AssistantStep(tool=AssistantToolName.COMPARE_AREAS, arguments={
                "area_slugs": [area.slug for area in areas],
                "include_municipality_benchmark": True,
                "filters": filters.model_dump(),
            }),
            AssistantStep(
                tool=AssistantToolName.DESCRIBE_METRIC,
                arguments={"metric_key": "vacancy_rate"},
            ),
        ])
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.COMPARE_AREAS, steps=steps),
            areas, filters, "COMPARISON_KNOWLEDGE",
        )

    area = areas[0] if len(areas) == 1 else None
    if area and asks_explanation and _has(normalized, "gastronomie", "restaurant"):
        if _has(normalized, "zeige", "anzeigen", "karte"):
            steps = _resolve_steps([area]) + [
                AssistantStep(tool=AssistantToolName.SEARCH_FEATURES, arguments={
                    "area_slug": area.slug,
                    "filters": filters.model_dump(),
                    "geometry_filter": "POLYGONS_ONLY" if _has(
                        normalized, "fläche", "flächen", "flaeche", "flaechen"
                    ) else "ALL",
                    "limit": 200,
                }),
                AssistantStep(
                    tool=AssistantToolName.DESCRIBE_CATEGORY,
                    arguments={"category": "gastronomy"},
                ),
            ]
            return _PreparedPlan(
                AssistantPlan(intent=AssistantIntent.SHOW_FEATURES, steps=steps),
                [area], filters, "MAP_KNOWLEDGE",
            )
        if _has(normalized, "wie viele", "anzahl"):
            steps = _resolve_steps([area]) + [
                AssistantStep(tool=AssistantToolName.GET_AREA_ANALYTICS, arguments={
                    "slug": area.slug, "filters": filters.model_dump(),
                }),
                AssistantStep(
                    tool=AssistantToolName.DESCRIBE_CATEGORY,
                    arguments={"category": "gastronomy"},
                ),
            ]
            return _PreparedPlan(
                AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=steps),
                [area], filters, "COMBINED_GASTRONOMY",
            )
    if area and asks_explanation and _has(normalized, "leerstandsquote"):
        steps = _resolve_steps([area]) + [
            AssistantStep(tool=AssistantToolName.GET_AREA_ANALYTICS, arguments={
                "slug": area.slug, "filters": filters.model_dump(),
            }),
            AssistantStep(
                tool=AssistantToolName.DESCRIBE_METRIC,
                arguments={"metric_key": "vacancy_rate"},
            ),
        ]
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=steps),
            [area], filters, "COMBINED_VACANCY",
        )

    if not asks_explanation:
        return None
    if _has(normalized, "unterschied") and _has(normalized, "osm", "openstreetmap") and _has(
        normalized, "stadtplaner"
    ):
        return _PreparedPlan(
            AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[AssistantStep(
                tool=AssistantToolName.LIST_KNOWN_DATASETS, arguments={}
            )]), [], filters, "DATASETS",
        )
    matches = retrieve_knowledge(normalized, limit=5)
    if not matches:
        return None
    exact = next((match for match in matches if match.confidence == "EXACT"), None)
    if exact is not None:
        step = AssistantStep(
            tool=AssistantToolName.GET_CONCEPT, arguments={"key": exact.entry.key}
        )
    else:
        step = AssistantStep(
            tool=AssistantToolName.SEARCH_KNOWLEDGE,
            arguments={"query": normalized, "limit": min(5, len(matches))},
        )
    return _PreparedPlan(
        AssistantPlan(intent=AssistantIntent.ANSWER_QUESTION, steps=[step]),
        [], filters, "KNOWLEDGE",
    )


def _provider_topic(plan: AssistantPlan) -> str:
    tools = {step.tool for step in plan.steps}
    if tools & {
        AssistantToolName.SEARCH_KNOWLEDGE, AssistantToolName.GET_CONCEPT,
        AssistantToolName.DESCRIBE_CATEGORY, AssistantToolName.DESCRIBE_METRIC,
        AssistantToolName.DESCRIBE_FILTER, AssistantToolName.LIST_KNOWN_DATASETS,
    }:
        return "KNOWLEDGE"
    if AssistantToolName.GET_OSM_FEATURE_DETAIL in tools:
        return "OSM_EXPLANATION"
    if AssistantToolName.SEARCH_FEATURES in tools:
        return "FEATURES"
    if AssistantToolName.GET_AREA_DETAIL in tools:
        return "AREA_DETAIL"
    if AssistantToolName.GET_AREA_ANALYTICS in tools:
        return "ANALYTICS"
    if AssistantToolName.GET_STATISTIC_SERIES in tools:
        return "STATISTIC_SERIES"
    if AssistantToolName.GET_AREA_STATISTICS in tools:
        return "STATISTICS_OVERVIEW"
    return "PROVIDER"


def _out_of_scope(normalized: str) -> bool:
    return _has(
        normalized, "gedicht", "lasagne", "kochen", "wahl gewinnen",
        "wetter morgen", "fußball", "fussball",
    )


def _claims(
    answer: str, prepared: _PreparedPlan, results: list[tuple[AssistantToolName, Any]]
) -> list[AssistantClaim]:
    evidence: list[AssistantEvidence] = []
    for tool, result in results:
        if tool == AssistantToolName.GET_AREA_ANALYTICS:
            evidence.append(AssistantEvidence(
                type="AREA_ANALYTICS",
                area_slug=prepared.areas[0].slug if prepared.areas else None,
                field=prepared.topic,
            ))
        elif tool == AssistantToolName.COMPARE_AREAS:
            evidence.append(AssistantEvidence(type="AREA_COMPARISON"))
        elif tool in {
            AssistantToolName.GET_AREA_STATISTICS,
            AssistantToolName.GET_STATISTIC_SERIES,
        }:
            evidence.append(AssistantEvidence(
                type="STATISTICS",
                area_slug=prepared.areas[0].slug if prepared.areas else None,
                field=prepared.metric_key,
            ))
        elif tool in {
            AssistantToolName.SEARCH_KNOWLEDGE, AssistantToolName.GET_CONCEPT,
            AssistantToolName.DESCRIBE_CATEGORY, AssistantToolName.DESCRIBE_METRIC,
            AssistantToolName.DESCRIBE_FILTER, AssistantToolName.LIST_KNOWN_DATASETS,
        }:
            for item in result.get("items", [])[:5]:
                evidence.append(AssistantEvidence(
                    type="KNOWLEDGE", knowledge_key=item.get("key")
                ))
        elif tool == AssistantToolName.GET_OSM_FEATURE_DETAIL:
            data = result.get("data", {})
            evidence.append(AssistantEvidence(
                type="OSM", osm_type=data.get("osm_type"), osm_id=data.get("osm_id")
            ))
    return [AssistantClaim(text=answer, evidence=evidence[:8])] if evidence else []


def _follow_up_actions(prepared: _PreparedPlan) -> list[AssistantFollowUpAction]:
    actions: list[AssistantFollowUpAction] = []
    if prepared.areas and prepared.topic not in {"FEATURES", "POLYGON_FEATURES", "MAP_KNOWLEDGE"}:
        area = prepared.areas[0]
        actions.append(AssistantFollowUpAction(
            type="SHOW_ON_MAP", label="Auf Karte anzeigen",
            query=f"Bitte {area.name} auf der Karte anzeigen",
        ))
    if prepared.topic in {"GASTRONOMY_COUNT", "FEATURES", "POLYGON_FEATURES"}:
        actions.append(AssistantFollowUpAction(
            type="EXPLAIN_CONCEPT", label="Kategorie erklären",
            query="Was zählt als Gastronomie?",
        ))
    if prepared.areas and prepared.topic and prepared.topic.startswith("STATISTIC"):
        area = prepared.areas[0]
        if prepared.metric_key and not prepared.topic.startswith("STATISTIC_SERIES"):
            title = STATISTIC_METRICS.get(prepared.metric_key, ("Kennzahl", ()))[0]
            actions.append(AssistantFollowUpAction(
                type="SHOW_STATISTICS", label="Entwicklung anzeigen",
                query=f"Zeigen Sie die Entwicklung {title} in {area.name}",
            ))
        actions.append(AssistantFollowUpAction(
            type="SHOW_DATA_SOURCE", label="Quelle erklären",
            query=f"Erkläre die Quelle der kommunalen Statistik für {area.name}",
        ))
    return actions


def _presentation_behavior(
    prepared: _PreparedPlan,
) -> AssistantPresentationBehavior:
    if prepared.plan.response_mode in {
        AssistantResponseMode.CLARIFICATION,
        AssistantResponseMode.REFUSAL,
    }:
        return AssistantPresentationBehavior.KEEP_OPEN
    if prepared.plan.intent in {
        AssistantIntent.CHANGE_FILTERS,
        AssistantIntent.LIST_AREAS,
    } or prepared.topic == "AREA_DETAIL":
        return AssistantPresentationBehavior.AUTO_CLOSE
    return AssistantPresentationBehavior.KEEP_OPEN


def _is_forbidden(normalized: str) -> bool:
    extra = (
        r"\b(admin|audit\s*logs?|systemanweisung)\b",
        r"\b(lösche|loesche|ändere|aendere|setze)\b",
        r"\b(select|drop|delete|insert|update|truncate|sql)\b",
        r"\b(eigentümer(?:daten)?|eigentuemer(?:daten)?|owner_name|price_per_sqm)\b",
        r"\b(secrets?|groq_api_key|database_url|environment\s*variablen?)\b",
    )
    return any(re.search(pattern, normalized) for pattern in (*FORBIDDEN_PATTERNS, *extra))


def _assistant_error_code(tool_code: str) -> str:
    if tool_code == "AREA_NOT_FOUND":
        return "ASSISTANT_AREA_NOT_FOUND"
    if tool_code in {
        "STATISTICS_NOT_FOUND", "STATISTIC_NOT_FOUND", "POLYGON_NOT_FOUND",
        "OSM_FEATURE_NOT_FOUND",
    }:
        return "ASSISTANT_DATA_UNAVAILABLE"
    return tool_code


def _refusal() -> _PreparedPlan:
    return _PreparedPlan(
        AssistantPlan(
            intent=AssistantIntent.UNSUPPORTED,
            response_mode=AssistantResponseMode.REFUSAL,
        ),
        [],
        SearchFilters(),
        error_code="ASSISTANT_QUERY_UNSUPPORTED",
    )


def _unsupported(
    message: str, *, code: str = "ASSISTANT_QUERY_UNSUPPORTED"
) -> _PreparedPlan:
    plan = AssistantPlan(intent=AssistantIntent.UNSUPPORTED, steps=[])
    return _PreparedPlan(plan, [], SearchFilters(), message=message, error_code=code)


def _clarification(message: str, areas: list[SearchArea]) -> _PreparedPlan:
    plan = AssistantPlan(
        intent=AssistantIntent.UNSUPPORTED,
        response_mode=AssistantResponseMode.CLARIFICATION,
    )
    return _PreparedPlan(
        plan, areas, SearchFilters(), message=message,
        error_code="ASSISTANT_AREA_AMBIGUOUS",
    )


def _metric_clarification(
    message: str,
    areas: list[SearchArea],
    filters: SearchFilters,
    choices: list[dict[str, Any]],
) -> _PreparedPlan:
    plan = AssistantPlan(
        intent=AssistantIntent.UNSUPPORTED,
        response_mode=AssistantResponseMode.CLARIFICATION,
    )
    return _PreparedPlan(
        plan, areas, filters, topic="STATISTIC_CLARIFICATION",
        message=message, error_code="ASSISTANT_METRIC_AMBIGUOUS",
        choices=choices,
    )

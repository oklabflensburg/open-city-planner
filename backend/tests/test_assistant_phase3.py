import json
import logging
import uuid
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.assistant import (
    AssistantContext,
    AssistantPlan,
    AssistantQueryRequest,
    AssistantToolName,
    KnowledgeToolResult,
    ResolveAreaResult,
    SearchFeaturesToolResult,
    ToolDataResult,
)
from app.schemas.search import SearchArea, SearchAreaType
from app.services import assistant
from app.services.assistant import answer_assistant_query
from app.services.assistant_explanations import explain_osm_feature
from app.services.assistant_knowledge import (
    KNOWLEDGE_CATALOG,
    KNOWLEDGE_VERSION,
    get_knowledge,
    retrieve_knowledge,
)
from app.services.assistant_provider import (
    ASSISTANT_PROMPT_VERSION,
    AssistantProviderError,
    GroqProvider,
)
from app.services.assistant_tools import ASSISTANT_TOOL_REGISTRY

ALTSTADT = SearchArea(
    id=str(uuid.UUID("11111111-1111-4111-8111-111111111111")),
    slug="altstadt-15630273",
    name="Altstadt",
    area_type=SearchAreaType.DISTRICT,
)


@pytest.mark.parametrize(
    ("query", "key"),
    [
        ("Restaurant", "category.gastronomy"),
        ("Restaurants", "category.gastronomy"),
        ("Gaststätte", "category.gastronomy"),
        ("Gasronomie", "category.gastronomy"),
        ("Gastrnomie", "category.gastronomy"),
        ("leerstehend", "occupancy.VACANT"),
        ("Leerstand", "occupancy.VACANT"),
        ("Open Street Map", "data_source.OSM"),
        ("OSM", "data_source.OSM"),
        ("Stadtviertel", "area_type.QUARTER"),
        ("Stadtteil", "area_type.DISTRICT"),
        ("Erdgeschoss", "filter.floor.EG"),
        ("Filialist", "filter.business_structure.CHAIN"),
        ("inhabergeführt", "filter.business_structure.INDEPENDENT"),
        ("Einzelhandelsdichte", "metric.retail_area_density_m2_per_km2"),
    ],
)
def test_controlled_knowledge_retrieval(query: str, key: str) -> None:
    matches = retrieve_knowledge(query)
    assert matches
    assert matches[0].entry.key == key
    assert matches[0].confidence in {"EXACT", "HIGH"}


def test_knowledge_catalog_tracks_canonical_categories_and_has_version() -> None:
    category_values = {
        entry.canonical_value for entry in KNOWLEDGE_CATALOG if entry.type == "CATEGORY"
    }
    from app.services.search_catalog import SEARCH_CATALOG

    assert category_values == set(SEARCH_CATALOG.categories)
    assert len(KNOWLEDGE_VERSION) == 12
    assert get_knowledge("occupancy.UNKNOWN") is not None


def test_knowledge_sources_are_explicitly_allowlisted_and_public() -> None:
    allowed_prefixes = ("backend/app/services/", "backend/app/schemas/", "docs/")
    forbidden = (".env", "auth", "users", "owner", "admin", "email")
    assert all(entry.source_path.startswith(allowed_prefixes) for entry in KNOWLEDGE_CATALOG)
    assert all(not any(term in entry.source_path.casefold() for term in forbidden) for entry in KNOWLEDGE_CATALOG)


def test_eval_dataset_contains_required_breadth() -> None:
    path = Path(__file__).parent / "fixtures" / "assistant_eval_cases.json"
    cases = json.loads(path.read_text())
    assert len(cases) >= 30
    assert all({"query", "expected_intent", "expected_tools"} <= case.keys() for case in cases)


def test_osm_explanation_uses_actual_mapping_and_unknown_semantics() -> None:
    gastronomy = explain_osm_feature({
        "osm_type": "node", "osm_id": 7, "name": "Bistro",
        "tags": {"amenity": "restaurant"},
    })
    assert gastronomy["category"] == "gastronomy"
    assert "amenity=restaurant" in gastronomy["category_explanation"]
    assert gastronomy["occupancy_status"] == "UNKNOWN"
    assert "nicht OCCUPIED" in gastronomy["occupancy_explanation"]

    vacant = explain_osm_feature({
        "osm_type": "way", "osm_id": 8, "tags": {"disused:shop": "clothes"},
    })
    assert vacant["occupancy_status"] == "VACANT"
    assert "disused:shop=clothes" in vacant["occupancy_explanation"]


@pytest.mark.parametrize(
    ("geometry_type", "coordinates"),
    [
        ("Point", [9.43, 54.78]),
        ("LineString", [[9.43, 54.78], [9.44, 54.79]]),
        ("Polygon", [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]]),
    ],
)
def test_feature_tool_result_accepts_public_osm_geometries(
    geometry_type: str, coordinates: list,
) -> None:
    result = SearchFeaturesToolResult.model_validate({
        "data": {
            "feature_collection": {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "id": "OSM:node:7",
                    "geometry": {"type": geometry_type, "coordinates": coordinates},
                    "properties": {
                        "source": "OSM",
                        "occupancy_status": "VACANT",
                    },
                }],
            },
            "bounds": [9.3, 54.7, 9.6, 54.9],
        },
    })

    assert result.data.feature_collection.features[0].geometry["type"] == geometry_type


async def _areas(_session: object, normalized: str) -> list[SearchArea]:
    return [ALTSTADT] if "altstadt" in normalized else []


@pytest.mark.asyncio
async def test_combined_data_and_knowledge_uses_three_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assistant, "_mentioned_areas", _areas)

    async def execute(_session: object, tool: AssistantToolName, _arguments: dict):
        if tool == AssistantToolName.RESOLVE_AREA:
            return ResolveAreaResult(status="resolved", area=ALTSTADT)
        if tool == AssistantToolName.GET_AREA_ANALYTICS:
            return ToolDataResult(data={"metrics": {"polygon_count": 17}})
        if tool == AssistantToolName.DESCRIBE_CATEGORY:
            return KnowledgeToolResult(
                items=[get_knowledge("category.gastronomy").public_dict()]
            )
        raise AssertionError(tool)

    monkeypatch.setattr(assistant, "execute_assistant_tool", execute)
    response = await answer_assistant_query(
        object(),  # type: ignore[arg-type]
        AssistantQueryRequest(
            query="Wie viele Gastronomieflächen gibt es in der Altstadt und was zählt als Gastronomie?"
        ),
    )

    assert [step.tool for step in response.plan.steps] == [
        "resolve_area", "get_area_analytics", "describe_category",
    ]
    assert response.presentation.value == 17
    assert "17" in response.answer
    assert any(source.type == "KNOWLEDGE" for source in response.sources_used)
    assert response.claims[0].evidence


@pytest.mark.asyncio
async def test_selected_osm_feature_is_loaded_server_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assistant, "_mentioned_areas", _areas)
    called: dict = {}

    async def execute(_session: object, tool: AssistantToolName, arguments: dict):
        called.update(arguments)
        return ToolDataResult(data={
            "osm_type": "node", "osm_id": 7, "name": "Bistro",
            "category_explanation": "amenity=restaurant erklärt Gastronomie.",
            "occupancy_explanation": "Der Status ist unbekannt.",
        })

    monkeypatch.setattr(assistant, "execute_assistant_tool", execute)
    context = AssistantContext(
        selected_osm_feature={"osm_type": "node", "osm_id": 7}
    )
    response = await answer_assistant_query(
        object(),  # type: ignore[arg-type]
        AssistantQueryRequest(query="Warum zählt das als Gastronomie?", context=context),
    )
    assert called == {"osm_type": "node", "osm_id": 7}
    assert "amenity=restaurant" in response.answer
    assert response.presentation.type == "KNOWLEDGE"


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        ai_search_enabled=True,
        ai_search_provider="groq",
        ai_search_model="configured-model",
        groq_api_key="secret-value",
        groq_max_retries=0,
        **overrides,
    )


def _completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
    })


@pytest.mark.asyncio
async def test_groq_provider_validates_structured_plan_and_usage() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-value"
        body = json.loads(request.content)
        assert body["model"] == "configured-model"
        assert body["response_format"]["type"] == "json_schema"
        return _completion('{"intent":"ANSWER_QUESTION","steps":[],"response_mode":"ANSWER"}')

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.test/v1"
    ) as client:
        provider = GroqProvider(_settings(), client)
        plan = await provider.plan("Fachfrage", AssistantContext(), [])
    assert plan.intent == "ANSWER_QUESTION"
    assert provider.usage["total_tokens"] == 14
    assert ASSISTANT_PROMPT_VERSION == "3.0"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "ASSISTANT_PROVIDER_UNAVAILABLE"),
        (401, "ASSISTANT_PROVIDER_UNAVAILABLE"),
        (429, "ASSISTANT_RATE_LIMITED"),
        (500, "ASSISTANT_PROVIDER_UNAVAILABLE"),
        (503, "ASSISTANT_PROVIDER_UNAVAILABLE"),
    ],
)
async def test_groq_provider_maps_http_errors_without_leaking_secret(
    status: int, code: str, caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.assistant_provider")
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": "secret-value"}})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.test/v1"
    ) as client:
        provider = GroqProvider(_settings(), client)
        with pytest.raises(AssistantProviderError) as raised:
            await provider.plan("Fachfrage", AssistantContext(), [])
    assert raised.value.code == code
    assert "secret-value" not in str(raised.value)
    assert f"status={status}" in caplog.text
    assert "response=" in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "secret-value" not in caplog.text


@pytest.mark.asyncio
async def test_provider_failure_is_visible_in_privacy_safe_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assistant, "_mentioned_areas", _areas)

    class FailingProvider:
        name = "groq"

        def __init__(self) -> None:
            self.usage = {"total_tokens": 99}

        async def plan(self, *_args: object) -> AssistantPlan:
            raise AssistantProviderError(
                "ASSISTANT_PROVIDER_UNAVAILABLE", "nicht verfügbar"
            )

    response = await answer_assistant_query(
        object(),  # type: ignore[arg-type]
        AssistantQueryRequest(query="Komplexe unbekannte Fachfrage"),
        provider=FailingProvider(),
    )

    assert response.error_code == "ASSISTANT_PROVIDER_UNAVAILABLE"
    assert response.telemetry.llm_used is True
    assert response.telemetry.provider == "groq"
    assert response.telemetry.success is False


@pytest.mark.asyncio
async def test_groq_provider_rejects_empty_and_malformed_output_after_one_repair(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.assistant_provider")
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _completion("{}" if calls == 1 else "kein json")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.test/v1"
    ) as client:
        provider = GroqProvider(_settings(), client)
        with pytest.raises(AssistantProviderError) as raised:
            await provider.plan("Fachfrage", AssistantContext(), [])
    assert raised.value.code == "ASSISTANT_INVALID_PLAN"
    assert calls == 2
    assert "assistant_provider_invalid_plan" in caplog.text
    assert "response={}" in caplog.text
    assert "response=kein json" in caplog.text


@pytest.mark.asyncio
async def test_groq_provider_maps_network_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.test/v1"
    ) as client:
        provider = GroqProvider(_settings(), client)
        with pytest.raises(AssistantProviderError) as raised:
            await provider.plan("Fachfrage", AssistantContext(), [])
    assert raised.value.code == "ASSISTANT_PROVIDER_UNAVAILABLE"
    assert raised.value.retryable is True


def test_unknown_provider_tool_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        AssistantPlan.model_validate({
            "intent": "ANSWER_QUESTION",
            "steps": [{"tool": "get_admin_users", "arguments": {}}],
        })


def test_phase3_tool_registry_contains_no_private_or_mutating_tools() -> None:
    forbidden = {
        "get_admin_users", "auth", "notifications", "email", "create_polygon",
        "update_polygon", "delete_polygon", "sql",
    }
    names = {tool.value for tool in ASSISTANT_TOOL_REGISTRY}
    assert names.isdisjoint(forbidden)
    assert {
        "search_knowledge", "get_concept", "describe_category", "describe_metric",
        "describe_filter", "list_known_datasets", "get_osm_feature_detail",
    } <= names


@pytest.mark.parametrize(
    ("tool_code", "public_code"),
    [
        ("AREA_NOT_FOUND", "ASSISTANT_AREA_NOT_FOUND"),
        ("STATISTIC_NOT_FOUND", "ASSISTANT_DATA_UNAVAILABLE"),
        ("ASSISTANT_KNOWLEDGE_NOT_FOUND", "ASSISTANT_KNOWLEDGE_NOT_FOUND"),
    ],
)
def test_internal_tool_errors_are_mapped_to_stable_assistant_codes(
    tool_code: str, public_code: str,
) -> None:
    assert assistant._assistant_error_code(tool_code) == public_code


def test_groq_secret_is_masked_in_settings_representation() -> None:
    settings = _settings()
    assert "secret-value" not in repr(settings)
    assert settings.groq_api_key is not None
    assert settings.groq_api_key.get_secret_value() == "secret-value"

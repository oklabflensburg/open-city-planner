import httpx
import pytest

from app.core.config import Settings
from app.modules.analysis_areas.application.legacy_queries import _read
from app.services.wikidata_enrichment import (
    Match,
    WikidataClient,
    WikidataEnrichmentService,
    WikidataEntity,
    _wikipedia_title,
)


def entity_payload(qid: str = "Q482", *, sitelink: bool = True) -> dict:
    return {
        "entities": {
            qid: {
                "id": qid,
                "labels": {"de": {"value": "Flensburg"}},
                "descriptions": {"de": {"value": "kreisfreie Stadt in Schleswig-Holstein"}},
                "aliases": {"de": [{"value": "Flensborg"}]},
                "claims": {
                    "P625": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"latitude": 54.78, "longitude": 9.43}}}}]
                },
                "sitelinks": {"dewiki": {"title": "Flensburg"}} if sitelink else {},
            }
        }
    }


@pytest.mark.asyncio
async def test_osm_wikidata_is_preferred_and_dewiki_sitelink_is_used() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        return httpx.Response(200, json=entity_payload())

    settings = Settings(redis_enabled=False, wikidata_api_url="https://www.wikidata.org/w/api.php")
    service = WikidataEnrichmentService(WikidataClient(settings, httpx.MockTransport(handler)))
    match = await service.resolve_area({
        "name": "Flensburg", "area_type": "MUNICIPALITY", "latitude": 54.78,
        "longitude": 9.43, "source_osm_wikidata": "Q482",
        "source_osm_wikipedia": "de:Anderer Artikel", "parent_name": None,
        "municipality_name": "Flensburg", "parent_wikidata_id": None,
    })
    assert match == Match("AUTO_MATCHED", "OSM_WIKIDATA", 1.0, match.entity)
    assert match.entity and match.entity.wikipedia_title == "Flensburg"
    assert calls[0]["action"] == "wbgetentities"
    assert calls[0]["ids"] == "Q482"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_osm_wikipedia_resolves_qid_without_guessing_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["sites"] == "dewiki"
        assert request.url.params["titles"] == "Flensburg"
        return httpx.Response(200, json=entity_payload())

    client = WikidataClient(Settings(redis_enabled=False), httpx.MockTransport(handler))
    service = WikidataEnrichmentService(client)
    match = await service.resolve_area({
        "name": "Flensburg", "area_type": "MUNICIPALITY", "latitude": 54.78,
        "longitude": 9.43, "source_osm_wikidata": None,
        "source_osm_wikipedia": "de:Flensburg", "parent_name": None,
        "municipality_name": "Flensburg", "parent_wikidata_id": None,
    })
    assert match.source == "OSM_WIKIPEDIA"
    assert match.entity and match.entity.id == "Q482"


@pytest.mark.asyncio
async def test_invalid_osm_wikidata_does_not_fall_back_to_search() -> None:
    class Client:
        async def search(self, _query: str) -> list[WikidataEntity]:
            raise AssertionError("invalid explicit OSM IDs must not trigger search")

    match = await WikidataEnrichmentService(Client()).resolve_area({
        "name": "Flensburg", "source_osm_wikidata": "Q1;Q2", "source_osm_wikipedia": None,
    })
    assert match == Match("INVALID", "OSM_WIKIDATA")


@pytest.mark.asyncio
async def test_missing_explicit_osm_entity_does_not_fall_back_to_search() -> None:
    class Client:
        async def entity(self, qid: str) -> None:
            assert qid == "Q999999999999999999"

        async def search(self, _query: str) -> list[WikidataEntity]:
            raise AssertionError("missing explicit OSM IDs must not trigger search")

    match = await WikidataEnrichmentService(Client()).resolve_area({
        "name": "Flensburg", "source_osm_wikidata": "Q999999999999999999",
        "source_osm_wikipedia": None,
    })
    assert match == Match("NOT_FOUND", "OSM_WIKIDATA")


@pytest.mark.asyncio
async def test_conflicting_osm_wikidata_and_wikipedia_are_marked() -> None:
    class Client:
        async def entity(self, qid: str) -> WikidataEntity:
            return WikidataEntity(qid, "Lutherpark", None, "Lutherpark (Flensburg)")

        async def entity_from_dewiki(self, _title: str) -> WikidataEntity:
            return WikidataEntity("Q42", "Douglas Adams", None, "Douglas Adams")

    match = await WikidataEnrichmentService(Client()).resolve_area({
        "name": "Lutherpark", "source_osm_wikidata": "Q19965387",
        "source_osm_wikipedia": "de:Lutherpark (Flensburg)",
    })
    assert match.status == "CONFLICT"
    assert match.source == "OSM_WIKIDATA"
    assert match.entity and match.entity.id == "Q19965387"


@pytest.mark.asyncio
async def test_search_retries_plain_name_but_keeps_contextual_validation() -> None:
    class Client:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, query: str) -> list[WikidataEntity]:
            self.queries.append(query)
            if query != "Innenstadt":
                return []
            return [WikidataEntity(
                "Q1", "Innenstadt", "Stadtteil von Flensburg", "Innenstadt (Flensburg)",
                latitude=54.781, longitude=9.431, parent_ids=("Q482",),
            )]

    client = Client()
    match = await WikidataEnrichmentService(client).resolve_area({
        "name": "Innenstadt", "area_type": "DISTRICT", "latitude": 54.78,
        "longitude": 9.43, "source_osm_wikidata": None, "source_osm_wikipedia": None,
        "parent_name": "Flensburg", "municipality_name": "Flensburg",
        "parent_wikidata_id": "Q482",
    })
    assert client.queries == ["Innenstadt Flensburg Flensburg Deutschland", "Innenstadt"]
    assert match.source == "WIKIDATA_SEARCH"


def test_search_validation_requires_name_location_and_parent_context() -> None:
    area = {
        "name": "Innenstadt", "area_type": "DISTRICT", "latitude": 54.78,
        "longitude": 9.43, "parent_name": "Flensburg", "parent_wikidata_id": "Q482",
        "municipality_name": "Flensburg",
    }
    correct = WikidataEntity(
        "Q1", "Innenstadt", "Stadtteil von Flensburg", None,
        latitude=54.781, longitude=9.431, parent_ids=("Q482",),
    )
    distant = WikidataEntity(
        "Q2", "Innenstadt", "Stadtteil einer anderen Stadt", None,
        latitude=52.5, longitude=13.4,
    )
    assert WikidataEnrichmentService.validate_candidate(area, correct) == 1.0
    assert WikidataEnrichmentService.validate_candidate(area, distant) == 0.0


def test_only_german_osm_wikipedia_values_are_accepted() -> None:
    assert _wikipedia_title("de:Flensburg") == "Flensburg"
    assert _wikipedia_title("https://de.wikipedia.org/wiki/Flensburg") == "Flensburg"
    assert _wikipedia_title("en:Flensburg") is None


def test_public_dto_only_builds_allowlisted_urls_for_publishable_match() -> None:
    row = {
        "id": "id", "slug": "flensburg", "name": "Flensburg", "area_type": "MUNICIPALITY",
        "parent_id": None, "parent_name": None, "parent_slug": None, "area_m2": 1.0,
        "source": "OSM", "updated_at": "2026-08-17T00:00:00Z", "child_count": 0,
        "public_wikidata_id": "Q482", "public_wikipedia_title": "Flensburg",
    }
    result = _read(row)
    assert result.external_links.wikidata.url == "https://www.wikidata.org/wiki/Q482"
    assert result.external_links.wikipedia.url == "https://de.wikipedia.org/wiki/Flensburg"


def test_child_without_own_match_never_inherits_parent_external_links() -> None:
    row = {
        "id": "quarter-id", "slug": "kreuz", "name": "Kreuz", "area_type": "QUARTER",
        "parent_id": "district-id", "parent_name": "Nordstadt", "parent_slug": "nordstadt",
        "area_m2": 1.0, "source": "OSM", "updated_at": "2026-08-17T00:00:00Z",
        "child_count": 0, "public_wikidata_id": None, "public_wikipedia_title": None,
    }
    result = _read(row)
    assert result.parent_name == "Nordstadt"
    assert result.external_links.wikidata is None
    assert result.external_links.wikipedia is None


def test_wikipedia_title_is_safely_encoded_from_validated_sitelink() -> None:
    row = {
        "id": "id", "slug": "area", "name": "Area", "area_type": "DISTRICT",
        "parent_id": None, "parent_name": None, "parent_slug": None, "area_m2": 1.0,
        "source": "OSM", "updated_at": "2026-08-17T00:00:00Z", "child_count": 0,
        "public_wikidata_id": "Q1", "public_wikipedia_title": "Mürwik (Flensburg)",
    }
    result = _read(row)
    assert result.external_links.wikipedia.url == (
        "https://de.wikipedia.org/wiki/M%C3%BCrwik_(Flensburg)"
    )

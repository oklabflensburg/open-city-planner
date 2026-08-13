import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.user_polygon import UserPolygon
from app.schemas.osm import OsmObjectInfo
from app.services import osm_lookup
from app.services.osm_lookup import OsmLookupService, normalize_osm_tags, rank_osm_matches


def polygon() -> UserPolygon:
    return UserPolygon(
        uuid=uuid.uuid4(),
        slug="eg-holm-42",
        name="Testfläche",
        category="fashion",
        geometry=object(),
        properties={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "osm_external_fallback_enabled": False,
        "overpass_api_url": None,
        "overpass_user_agent": "Stadtplaner tests",
        "overpass_timeout_seconds": 1.0,
        "osm_lookup_cache_ttl_seconds": 60,
        "osm_external_min_interval_seconds": 0.0,
        "osm_lookup_max_matches": 25,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normalizes_known_tags_and_keeps_missing_values_null() -> None:
    result = normalize_osm_tags(
        osm_type="way",
        osm_id=42,
        tags={
            "name": "Modehaus",
            "shop": "clothes",
            "contact:website": "https://example.org",
            "addr:street": "Holm",
            "private_note": "must not leak",
        },
        overlap_ratio=0.875,
    )

    assert result.name == "Modehaus"
    assert result.category == "shop"
    assert result.website == "https://example.org"
    assert result.phone is None
    assert result.address and result.address.street == "Holm"
    assert "private_note" not in result.tags


def test_ranking_prefers_complete_and_specific_match() -> None:
    building = OsmObjectInfo(
        osm_id=1, osm_type="way", category="building", building="yes", overlap_ratio=0.8
    )
    shop = OsmObjectInfo(
        osm_id=2, osm_type="node", category="shop", shop="clothes", overlap_ratio=1.0
    )
    assert rank_osm_matches([building, shop])[0].osm_id == 2


@pytest.mark.asyncio
async def test_local_match_prevents_external_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OsmLookupService()
    local = OsmObjectInfo(osm_id=2, osm_type="node", shop="clothes", category="shop")
    monkeypatch.setattr(osm_lookup, "get_settings", lambda: settings(
        osm_external_fallback_enabled=True, overpass_api_url="https://overpass.test"
    ))
    monkeypatch.setattr(service, "_local_matches", AsyncMock(return_value=[local]))
    external = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "_overpass_matches", external)

    result = await service._lookup(AsyncMock(), polygon())

    assert result.source == "local"
    assert result.primary_match == local
    external.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_local_lookup_respects_disabled_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OsmLookupService()
    monkeypatch.setattr(osm_lookup, "get_settings", lambda: settings())
    monkeypatch.setattr(service, "_local_matches", AsyncMock(return_value=[]))
    external = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "_overpass_matches", external)

    result = await service._lookup(AsyncMock(), polygon())

    assert result.source == "none"
    assert result.matches == []
    assert result.primary_match is None
    external.assert_not_awaited()


@pytest.mark.asyncio
async def test_configured_fallback_is_used_after_empty_local_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = OsmLookupService()
    external_match = OsmObjectInfo(osm_id=3, osm_type="node", amenity="cafe")
    monkeypatch.setattr(osm_lookup, "get_settings", lambda: settings(
        osm_external_fallback_enabled=True, overpass_api_url="https://overpass.test"
    ))
    monkeypatch.setattr(service, "_local_matches", AsyncMock(return_value=[]))
    external = AsyncMock(return_value=[external_match])
    monkeypatch.setattr(service, "_overpass_matches", external)

    result = await service._lookup(AsyncMock(), polygon())

    assert result.source == "overpass"
    assert result.primary_match == external_match
    external.assert_awaited_once()


@pytest.mark.asyncio
async def test_overpass_timeout_becomes_controlled_lookup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def post(self, *_args: object, **_kwargs: object):
            raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(osm_lookup, "get_settings", lambda: settings(
        osm_external_fallback_enabled=True, overpass_api_url="https://overpass.test"
    ))
    monkeypatch.setattr(osm_lookup.httpx, "AsyncClient", lambda **_kwargs: TimeoutClient())
    monkeypatch.setattr(osm_lookup, "from_wkb_element", lambda _geometry: {
        "type": "Polygon",
        "coordinates": [[(9.43, 54.78), (9.44, 54.78), (9.43, 54.79), (9.43, 54.78)]],
    })

    with pytest.raises(osm_lookup.OsmLookupError):
        await OsmLookupService()._overpass_matches(polygon())


@pytest.mark.asyncio
async def test_overpass_uses_geojson_mapping_and_normalizes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {
                "elements": [{
                    "type": "node",
                    "id": 123,
                    "lat": 54.785,
                    "lon": 9.435,
                    "tags": {"name": "Testladen", "shop": "clothes"},
                }]
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def post(self, url: str, *, data: dict[str, str]) -> Response:
            assert url == "https://overpass.test"
            assert 'poly:"54.7800000 9.4300000' in data["data"]
            return Response()

    monkeypatch.setattr(osm_lookup, "get_settings", lambda: settings(
        osm_external_fallback_enabled=True, overpass_api_url="https://overpass.test"
    ))
    def client_factory(**kwargs: object) -> Client:
        assert kwargs["headers"] == {
            "User-Agent": "Stadtplaner tests",
            "Accept": "application/json",
        }
        return Client()

    monkeypatch.setattr(osm_lookup.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(osm_lookup, "from_wkb_element", lambda _geometry: {
        "type": "Polygon",
        "coordinates": [[(9.43, 54.78), (9.44, 54.78), (9.43, 54.79), (9.43, 54.78)]],
    })

    matches = await OsmLookupService()._overpass_matches(polygon())

    assert len(matches) == 1
    assert matches[0].name == "Testladen"
    assert matches[0].shop == "clothes"


def test_local_query_uses_spatial_predicates_and_index_prefilter() -> None:
    query = str(osm_lookup.LOCAL_LOOKUP_SQL)
    assert "osm.geometry && target.geometry" in query
    assert "ST_Within" in query
    assert "ST_Intersects" in query
    assert "ST_Intersection" in query
    assert "ST_Transform" in query


@pytest.mark.asyncio
async def test_polygon_version_cache_prevents_repeated_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    osm_lookup._cache.clear()
    osm_lookup._inflight.clear()
    record = polygon()
    session = AsyncMock()
    session.scalar.return_value = record
    service = OsmLookupService()
    lookup = AsyncMock(
        return_value=osm_lookup.PolygonOsmInfo(
            polygon_id=str(record.uuid),
            polygon_slug=record.slug,
            source="none",
            matches=[],
        )
    )
    monkeypatch.setattr(service, "_lookup", lookup)
    monkeypatch.setattr(osm_lookup, "get_settings", lambda: settings())

    first = await service.find_osm_objects_for_polygon(session, slug=record.slug)
    second = await service.find_osm_objects_for_polygon(session, slug=record.slug)

    assert first == second
    lookup.assert_awaited_once()
    osm_lookup._cache.clear()

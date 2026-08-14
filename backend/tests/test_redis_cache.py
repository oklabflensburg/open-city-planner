import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.cache.keys import build_cache_key, viewport_tile_bucket
from app.cache.service import CacheService
from app.schemas.analytics import AnalyticsFastFacts, AnalyticsOverview, PrimeRentData
from app.schemas.osm import OsmViewportQuery
from app.services import analytics as analytics_service
from app.services import cache_versions
from app.services.analysis_area_api import areas_geojson
from app.services.osm_features import viewport_features


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def set(self, key: str, value: bytes, **kwargs) -> bool:
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        if kwargs.get("ex"):
            self.ttls[key] = kwargs["ex"]
        return True

    async def delete(self, *keys) -> int:
        count = sum(key in self.values for key in keys)
        for key in keys:
            self.values.pop(key, None)
        return count

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def eval(self, _script, _count, key, token):
        if self.values.get(key) == token:
            return await self.delete(key)
        return 0

    async def scan_iter(self, match: str, count: int = 10):
        prefix = match.rstrip("*")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key


class BrokenRedis(FakeRedis):
    async def get(self, key: str) -> bytes | None:
        raise ConnectionError(key)

    async def set(self, key: str, value: bytes, **kwargs) -> bool:
        raise ConnectionError(key)


@pytest.mark.asyncio
async def test_json_hit_miss_ttl_corruption_and_mget(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: redis)
    cache = CacheService()
    assert await cache.get_json("missing") is None
    assert await cache.set_json("one", {"value": 1}, 123)
    assert await cache.get_json("one") == {"value": 1}
    assert redis.ttls["one"] == 123
    redis.values["broken"] = b"{not-json"
    assert await cache.get_json("broken") is None
    assert "broken" not in redis.values
    assert await cache.get_many(["one", "missing"]) == [redis.values["one"], None]


@pytest.mark.asyncio
async def test_redis_failure_falls_back_and_stampede_computes_once(monkeypatch) -> None:
    cache = CacheService()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: BrokenRedis())
    assert await cache.get_json("key") is None
    fallback, status = await cache.get_or_compute(
        "fallback", ttl=60, resource="test", compute=AsyncMock(return_value={"db": True})
    )
    assert fallback == {"db": True}
    assert status == "MISS"
    calls = 0

    async def compute():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"ok": True}

    redis = FakeRedis()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: redis)
    results = await asyncio.gather(
        *(cache.get_or_compute("same", ttl=60, resource="test", compute=compute) for _ in range(10))
    )
    assert calls == 1
    assert all(result[0] == {"ok": True} for result in results)


def test_tile_bucket_reuses_near_viewports_and_keys_include_filters() -> None:
    first = viewport_tile_bucket(9.43001, 54.78001, 9.43901, 54.78901, 16)
    second = viewport_tile_bucket(9.43002, 54.78002, 9.43902, 54.78902, 16)
    assert {key: first[key] for key in ("tile_zoom", "x_min", "x_max", "y_min", "y_max")} == {
        key: second[key] for key in ("tile_zoom", "x_min", "x_max", "y_min", "y_max")
    }
    base = build_cache_key("osm:viewport", {"categories": ["retail"], "zoom": 16}, version=1)
    reordered = build_cache_key("osm:viewport", {"zoom": 16, "categories": ["retail"]}, version=1)
    changed = build_cache_key("osm:viewport", {"categories": ["retail"], "zoom": 17}, version=1)
    assert base == reordered
    assert base != changed


@pytest.mark.asyncio
async def test_osm_second_request_is_redis_hit_without_second_feature_query(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: redis)
    cache_versions._local_versions.clear()
    session = AsyncMock()
    session.scalar.return_value = 1
    imported_at = datetime(2026, 8, 13, tzinfo=UTC)

    class Rows:
        def mappings(self):
            return self

        def all(self):
            return [{
                "osm_type": "node", "osm_id": 1, "tags": {"name": "Café"},
                "category": "gastronomy", "dimension": 0, "imported_at": imported_at,
                "geometry": {"type": "Point", "coordinates": [9.435, 54.783]},
                "primary_type": "cafe", "linked_polygons": [],
            }]

    session.execute.return_value = Rows()
    query = OsmViewportQuery(
        west=9.43, south=54.78, east=9.44, north=54.79, zoom=16, limit=100
    )
    first = await viewport_features(session, query)
    second = await viewport_features(session, query)
    assert first == second
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_version_bump_is_persisted_for_namespace_invalidation() -> None:
    session = AsyncMock()
    await cache_versions.bump_cache_versions(session, ("analytics", "polygons"))
    assert session.execute.await_args.args[1] == {"names": ["analytics", "polygons"]}


@pytest.mark.asyncio
async def test_analysis_area_geojson_second_read_is_cached(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: redis)
    session = AsyncMock()

    class Rows:
        def mappings(self):
            return self

        def all(self):
            return [{
                "id": "area-1", "slug": "test", "name": "Test", "area_type": "QUARTER",
                "parent_id": 2, "area_m2": 10.0, "source": "OSM", "source_osm_type": "relation",
                "source_osm_id": 1, "source_admin_level": 10,
                "geometry": {"type": "MultiPolygon", "coordinates": []},
            }]

    session.execute.return_value = Rows()
    first = await areas_geojson(session)
    second = await areas_geojson(session)
    assert first == second
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_analytics_filters_share_cache_only_when_canonical_key_matches(monkeypatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: redis)
    monkeypatch.setattr(analytics_service, "cache_version", AsyncMock(return_value=7))
    result = AnalyticsOverview(
        fast_facts=AnalyticsFastFacts(shops=0),
        industry_distribution=[],
        category_counts=[],
        prime_rents=PrimeRentData(),
    )
    compute = AsyncMock(return_value=result)
    monkeypatch.setattr(analytics_service, "_analytics_overview_uncached", compute)
    session = AsyncMock()
    first = await analytics_service.analytics_overview(session, categories=("food", "fashion"))
    second = await analytics_service.analytics_overview(session, categories=("fashion", "food"))
    third = await analytics_service.analytics_overview(session, categories=("food",))
    assert first == second == third
    assert compute.await_count == 2

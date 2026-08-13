import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.user_polygon import UserPolygon
from app.schemas.osm import OsmAddress, OsmCentroid, OsmObjectInfo, PolygonOsmInfo
from app.services.geometry import from_wkb_element

logger = logging.getLogger(__name__)

RELEVANT_TAGS = (
    "name",
    "shop",
    "amenity",
    "office",
    "craft",
    "tourism",
    "leisure",
    "building",
    "building:levels",
    "brand",
    "operator",
    "opening_hours",
    "website",
    "contact:website",
    "phone",
    "contact:phone",
    "email",
    "contact:email",
    "wheelchair",
    "addr:street",
    "addr:housenumber",
    "addr:postcode",
    "addr:city",
    "level",
    "indoor",
    "ref",
)
CATEGORY_TAGS = ("shop", "amenity", "office", "craft", "tourism", "leisure", "building")

LOCAL_LOOKUP_SQL = text(
    """
    WITH target AS (
        SELECT geometry
        FROM user_polygons
        WHERE uuid = :polygon_id
    ), candidates AS (
        SELECT
            osm.osm_type,
            osm.osm_id,
            osm.tags,
            ST_Dimension(osm.geometry) = 0 AS is_point,
            CASE
                WHEN ST_Dimension(osm.geometry) = 0 THEN 1.0
                ELSE LEAST(
                    1.0,
                    ST_Area(
                        ST_Intersection(
                            ST_Transform(ST_MakeValid(osm.geometry), 25832),
                            ST_Transform(ST_MakeValid(target.geometry), 25832)
                        )
                    ) / NULLIF(
                        ST_Area(ST_Transform(ST_MakeValid(osm.geometry), 25832)),
                        0
                    )
                )
            END AS overlap_ratio,
            ST_X(ST_PointOnSurface(osm.geometry)) AS longitude,
            ST_Y(ST_PointOnSurface(osm.geometry)) AS latitude
        FROM osm_features AS osm
        CROSS JOIN target
        WHERE osm.geometry && target.geometry
          AND osm.tags ?| ARRAY[
              'name', 'shop', 'amenity', 'office', 'craft', 'tourism',
              'leisure', 'building'
          ]
          AND (
              (ST_Dimension(osm.geometry) = 0 AND ST_Within(osm.geometry, target.geometry))
              OR (
                  ST_Dimension(osm.geometry) = 2
                  AND ST_Intersects(osm.geometry, target.geometry)
                  AND ST_Area(
                      ST_Intersection(
                          ST_Transform(ST_MakeValid(osm.geometry), 25832),
                          ST_Transform(ST_MakeValid(target.geometry), 25832)
                      )
                  ) > 0
              )
          )
    )
    SELECT *
    FROM candidates
    ORDER BY overlap_ratio DESC NULLS LAST, is_point DESC, osm_type, osm_id
    LIMIT :candidate_limit
    """
)


class OsmLookupError(RuntimeError):
    pass


_cache: dict[tuple[str, str], tuple[float, PolygonOsmInfo]] = {}
_inflight: dict[tuple[str, str], asyncio.Task[PolygonOsmInfo]] = {}
_external_lock = asyncio.Lock()
_last_external_request = 0.0


def _text_value(tags: Mapping[str, Any], key: str) -> str | None:
    value = tags.get(key)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def normalize_osm_tags(
    *,
    osm_type: str,
    osm_id: int,
    tags: Mapping[str, Any],
    longitude: float | None = None,
    latitude: float | None = None,
    overlap_ratio: float | None = None,
) -> OsmObjectInfo:
    category = next((key for key in CATEGORY_TAGS if _text_value(tags, key)), None)
    address_values = {
        "street": _text_value(tags, "addr:street"),
        "house_number": _text_value(tags, "addr:housenumber"),
        "postal_code": _text_value(tags, "addr:postcode"),
        "city": _text_value(tags, "addr:city"),
    }
    address = OsmAddress(**address_values) if any(address_values.values()) else None
    centroid = (
        OsmCentroid(longitude=longitude, latitude=latitude)
        if longitude is not None and latitude is not None
        else None
    )
    public_tags = {
        key: value
        for key in RELEVANT_TAGS
        if (value := _text_value(tags, key)) is not None
    }
    return OsmObjectInfo(
        osm_id=osm_id,
        osm_type=osm_type,  # type: ignore[arg-type]
        name=_text_value(tags, "name"),
        category=category,
        shop=_text_value(tags, "shop"),
        amenity=_text_value(tags, "amenity"),
        office=_text_value(tags, "office"),
        craft=_text_value(tags, "craft"),
        tourism=_text_value(tags, "tourism"),
        leisure=_text_value(tags, "leisure"),
        building=_text_value(tags, "building"),
        building_levels=_text_value(tags, "building:levels"),
        brand=_text_value(tags, "brand"),
        operator=_text_value(tags, "operator"),
        opening_hours=_text_value(tags, "opening_hours"),
        website=_text_value(tags, "website") or _text_value(tags, "contact:website"),
        phone=_text_value(tags, "phone") or _text_value(tags, "contact:phone"),
        email=_text_value(tags, "email") or _text_value(tags, "contact:email"),
        wheelchair=_text_value(tags, "wheelchair"),
        level=_text_value(tags, "level"),
        indoor=_text_value(tags, "indoor"),
        ref=_text_value(tags, "ref"),
        address=address,
        centroid=centroid,
        overlap_ratio=round(overlap_ratio, 6) if overlap_ratio is not None else None,
        tags=public_tags,
    )


def rank_osm_matches(matches: list[OsmObjectInfo]) -> list[OsmObjectInfo]:
    def score(match: OsmObjectInfo) -> tuple[float, int, int, int]:
        overlap = match.overlap_ratio or 0.0
        specific = int(bool(match.category and match.category != "building"))
        named = int(bool(match.name))
        complete = int(overlap >= 0.999)
        return complete, overlap, specific, named

    return sorted(matches, key=score, reverse=True)


class OsmLookupService:
    async def find_osm_objects_for_polygon(
        self, session: AsyncSession, *, slug: str | None = None, polygon_id: str | None = None
    ) -> PolygonOsmInfo | None:
        statement = select(UserPolygon)
        if slug is not None:
            statement = statement.where(UserPolygon.slug == slug)
        elif polygon_id is not None:
            statement = statement.where(UserPolygon.uuid == polygon_id)
        else:
            raise ValueError("slug or polygon_id is required")
        polygon = await session.scalar(statement)
        if polygon is None:
            return None

        key = (str(polygon.uuid), polygon.updated_at.isoformat())
        cached = _cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        task = _inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._lookup(session, polygon))
            _inflight[key] = task
        try:
            result = await asyncio.shield(task)
        finally:
            if task.done():
                _inflight.pop(key, None)
        settings = get_settings()
        _cache[key] = (time.monotonic() + settings.osm_lookup_cache_ttl_seconds, result)
        self._discard_stale_cache_entries(str(polygon.uuid), keep=key)
        return result

    async def _lookup(self, session: AsyncSession, polygon: UserPolygon) -> PolygonOsmInfo:
        matches = await self._local_matches(session, str(polygon.uuid))
        source = "local"
        if not matches:
            source = "none"
            settings = get_settings()
            if settings.osm_external_fallback_enabled and settings.overpass_api_url:
                matches = await self._overpass_matches(polygon)
                source = "overpass" if matches else "none"
        ranked = rank_osm_matches(matches)
        return PolygonOsmInfo(
            polygon_id=str(polygon.uuid),
            polygon_slug=polygon.slug,
            source=source,
            matches=ranked,
            primary_match=ranked[0] if ranked else None,
        )

    async def _local_matches(
        self, session: AsyncSession, polygon_id: str
    ) -> list[OsmObjectInfo]:
        settings = get_settings()
        rows = (
            await session.execute(
                LOCAL_LOOKUP_SQL,
                {
                    "polygon_id": polygon_id,
                    "candidate_limit": max(settings.osm_lookup_max_matches * 4, 25),
                },
            )
        ).mappings().all()
        return [
            normalize_osm_tags(
                osm_type=row["osm_type"],
                osm_id=row["osm_id"],
                tags=row["tags"] or {},
                longitude=float(row["longitude"]) if row["longitude"] is not None else None,
                latitude=float(row["latitude"]) if row["latitude"] is not None else None,
                overlap_ratio=(
                    float(row["overlap_ratio"])
                    if row["overlap_ratio"] is not None
                    else None
                ),
            )
            for row in rows[: settings.osm_lookup_max_matches]
        ]

    async def _overpass_matches(self, polygon: UserPolygon) -> list[OsmObjectInfo]:
        settings = get_settings()
        geometry = from_wkb_element(polygon.geometry)
        coordinates = geometry.get("coordinates")
        if geometry.get("type") != "Polygon" or not isinstance(coordinates, (list, tuple)):
            raise OsmLookupError("Polygon geometry is unavailable for OpenStreetMap lookup")
        ring = list(coordinates[0]) if coordinates else []
        if len(ring) < 4:
            raise OsmLookupError("Polygon geometry is unavailable for OpenStreetMap lookup")
        if len(ring) > 100:
            step = max(1, len(ring) // 99)
            ring = ring[::step]
            original_last = coordinates[0][-1]
            if ring[-1] != original_last:
                ring.append(original_last)
        polygon_filter = " ".join(f"{lat:.7f} {lon:.7f}" for lon, lat in ring)
        query = (
            f'[out:json][timeout:{max(1, int(settings.overpass_timeout_seconds))}];'
            f'nwr[~"^(name|shop|amenity|office|craft|tourism|leisure|building)$"~"."]'
            f'(poly:"{polygon_filter}");out tags center;'
        )
        await self._respect_external_rate_limit(settings.osm_external_min_interval_seconds)
        try:
            async with httpx.AsyncClient(
                timeout=settings.overpass_timeout_seconds,
                headers={
                    "User-Agent": settings.overpass_user_agent,
                    "Accept": "application/json",
                },
            ) as client:
                response = await client.post(settings.overpass_api_url, data={"data": query})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Configured Overpass lookup failed for polygon_id=%s status=%s",
                polygon.uuid,
                status_code or "unavailable",
            )
            raise OsmLookupError("OpenStreetMap lookup failed") from exc

        matches: list[OsmObjectInfo] = []
        for element in payload.get("elements", []):
            osm_type = element.get("type")
            osm_id = element.get("id")
            tags = element.get("tags")
            if osm_type not in {"node", "way", "relation"} or not isinstance(osm_id, int):
                continue
            if not isinstance(tags, dict):
                continue
            center = element if osm_type == "node" else element.get("center", {})
            matches.append(
                normalize_osm_tags(
                    osm_type=osm_type,
                    osm_id=osm_id,
                    tags=tags,
                    longitude=center.get("lon"),
                    latitude=center.get("lat"),
                    overlap_ratio=1.0 if osm_type == "node" else None,
                )
            )
        return matches[: settings.osm_lookup_max_matches]

    async def _respect_external_rate_limit(self, interval: float) -> None:
        global _last_external_request
        async with _external_lock:
            remaining = interval - (time.monotonic() - _last_external_request)
            if remaining > 0:
                await asyncio.sleep(remaining)
            _last_external_request = time.monotonic()

    def _discard_stale_cache_entries(
        self, polygon_id: str, *, keep: tuple[str, str]
    ) -> None:
        for key in list(_cache):
            if key[0] == polygon_id and key != keep:
                _cache.pop(key, None)

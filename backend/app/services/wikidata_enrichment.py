import asyncio
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import unquote

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key
from app.cache.service import cache_service
from app.core.config import Settings, get_settings
from app.services.cache_versions import bump_cache_versions

QID_RE = re.compile(r"^Q[1-9][0-9]*$")
PUBLIC_STATUSES = {"VERIFIED", "AUTO_MATCHED"}
GEOGRAPHIC_DESCRIPTION_TERMS = (
    "stadt", "gemeinde", "stadtteil", "quartier", "ort", "gebiet", "district",
    "municipality", "borough", "neighborhood", "neighbourhood", "village",
)
NON_GEOGRAPHIC_DESCRIPTION_TERMS = (
    "person", "unternehmen", "company", "film", "album", "bahnhof", "station",
    "straße", "strasse", "road", "begriffsklärung", "disambiguation",
)


@dataclass
class WikidataEntity:
    id: str
    label: str | None
    description: str | None
    wikipedia_title: str | None
    aliases: tuple[str, ...] = ()
    latitude: float | None = None
    longitude: float | None = None
    parent_ids: tuple[str, ...] = ()


@dataclass
class Match:
    status: str
    source: str | None = None
    confidence: float | None = None
    entity: WikidataEntity | None = None


@dataclass
class WikidataEnrichmentReport:
    checked: int = 0
    osm_wikidata: int = 0
    osm_wikipedia: int = 0
    search: int = 0
    manual: int = 0
    not_found: int = 0
    ambiguous: int = 0
    conflicts: int = 0
    errors: list[str] = field(default_factory=list)


class WikidataClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.transport = transport

    async def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        cache_key = build_cache_key("wikidata", params, version=1)
        cached = await cache_service.get_json(cache_key)
        if cached is not None:
            return cached
        timeout = httpx.Timeout(self.settings.wikidata_timeout_seconds)
        headers = {"User-Agent": self.settings.wikidata_user_agent, "Accept": "application/json"}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=timeout, transport=self.transport, headers=headers) as client:
                    response = await client.get(self.settings.wikidata_api_url, params={**params, "format": "json", "formatversion": 2})
                if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
                    await asyncio.sleep(min(float(response.headers.get("Retry-After", attempt + 1)), 5.0))
                    continue
                response.raise_for_status()
                payload = response.json()
                ttl = self.settings.wikidata_cache_ttl_seconds
                if not payload.get("entities") and not payload.get("search"):
                    ttl = self.settings.wikidata_negative_cache_ttl_seconds
                await cache_service.set_json(cache_key, payload, ttl)
                return payload
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(attempt + 1)
        if last_error:
            raise last_error
        raise RuntimeError("Wikidata request failed")

    async def entity(self, qid: str) -> WikidataEntity | None:
        if not QID_RE.fullmatch(qid):
            return None
        payload = await self._request({
            "action": "wbgetentities", "ids": qid,
            "props": "labels|descriptions|aliases|claims|sitelinks/urls", "languages": "de|en",
            "sitefilter": "dewiki",
        })
        raw = payload.get("entities", {}).get(qid)
        return self._parse_entity(raw) if raw and not raw.get("missing") else None

    async def entity_from_dewiki(self, title: str) -> WikidataEntity | None:
        payload = await self._request({
            "action": "wbgetentities", "sites": "dewiki", "titles": title,
            "props": "labels|descriptions|aliases|claims|sitelinks/urls", "languages": "de|en",
            "sitefilter": "dewiki",
        })
        raw = next((value for value in payload.get("entities", {}).values() if not value.get("missing")), None)
        return self._parse_entity(raw) if raw else None

    async def search(self, query: str) -> list[WikidataEntity]:
        payload = await self._request({
            "action": "wbsearchentities", "search": query, "language": "de", "uselang": "de",
            "type": "item", "limit": self.settings.wikidata_search_limit,
        })
        ids = [item.get("id") for item in payload.get("search", []) if QID_RE.fullmatch(item.get("id", ""))]
        result: list[WikidataEntity] = []
        for qid in ids:
            entity = await self.entity(qid)
            if entity:
                result.append(entity)
        return result

    @staticmethod
    def _parse_entity(raw: dict[str, Any]) -> WikidataEntity:
        def localized(field: str) -> str | None:
            values = raw.get(field, {})
            return (values.get("de") or values.get("en") or {}).get("value")

        aliases = raw.get("aliases", {}).get("de") or raw.get("aliases", {}).get("en") or []
        coordinate = _claim_value(raw, "P625") or {}
        parent_ids = tuple(
            value["id"] for value in _claim_values(raw, "P131")
            if isinstance(value, dict) and QID_RE.fullmatch(value.get("id", ""))
        )
        sitelink = raw.get("sitelinks", {}).get("dewiki") or {}
        return WikidataEntity(
            id=raw["id"], label=localized("labels"), description=localized("descriptions"),
            wikipedia_title=sitelink.get("title"),
            aliases=tuple(item["value"] for item in aliases if item.get("value")),
            latitude=coordinate.get("latitude"), longitude=coordinate.get("longitude"),
            parent_ids=parent_ids,
        )


def _claim_values(raw: dict[str, Any], prop: str) -> list[Any]:
    values = []
    for claim in raw.get("claims", {}).get(prop, []):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            values.append(snak.get("datavalue", {}).get("value"))
    return values


def _claim_value(raw: dict[str, Any], prop: str) -> Any | None:
    values = _claim_values(raw, prop)
    return values[0] if values else None


def _wikipedia_title(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("de:"):
        return value[3:].strip().replace("_", " ") or None
    prefix = "https://de.wikipedia.org/wiki/"
    if value.startswith(prefix):
        return unquote(value[len(prefix):]).replace("_", " ") or None
    return None


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class WikidataEnrichmentService:
    def __init__(self, client: WikidataClient | None = None):
        self.client = client or WikidataClient()

    async def resolve_area(
        self, area: dict[str, Any], session: AsyncSession | None = None
    ) -> Match:
        osm_qid = (area.get("source_osm_wikidata") or "").strip()
        if QID_RE.fullmatch(osm_qid):
            entity = await self.client.entity(osm_qid)
            if entity:
                return Match("AUTO_MATCHED", "OSM_WIKIDATA", 1.0, entity)
        title = _wikipedia_title(area.get("source_osm_wikipedia"))
        if title:
            entity = await self.client.entity_from_dewiki(title)
            if entity:
                return Match("AUTO_MATCHED", "OSM_WIKIPEDIA", 0.95, entity)
        context = " ".join(filter(None, (area["name"], area.get("parent_name"), area.get("municipality_name"), "Deutschland")))
        candidates = await self.client.search(context)
        if not candidates:
            candidates = await self.client.search(area["name"])
        ranked = []
        for candidate in candidates:
            distance_km = await self._postgis_distance_km(session, area, candidate)
            ranked.append((self.validate_candidate(area, candidate, distance_km), candidate))
        ranked.sort(key=lambda item: item[0], reverse=True)
        accepted = [(score, candidate) for score, candidate in ranked if score >= 0.85]
        if not accepted:
            return Match("NOT_FOUND")
        if len(accepted) > 1 and accepted[0][0] - accepted[1][0] < 0.1:
            return Match("AMBIGUOUS")
        score, candidate = accepted[0]
        return Match("AUTO_MATCHED", "WIKIDATA_SEARCH", score, candidate)

    @staticmethod
    def validate_candidate(
        area: dict[str, Any], candidate: WikidataEntity, distance_km: float | None = None
    ) -> float:
        names = {candidate.label or "", *candidate.aliases}
        score = 0.35 if area["name"].casefold() in {name.casefold() for name in names} else 0.0
        description = (candidate.description or "").casefold()
        if any(term in description for term in NON_GEOGRAPHIC_DESCRIPTION_TERMS):
            return 0.0
        if candidate.latitude is not None and candidate.longitude is not None:
            distance = distance_km if distance_km is not None else _distance_km(
                area["latitude"], area["longitude"], candidate.latitude, candidate.longitude
            )
            maximum = 10.0 if area["area_type"] == "MUNICIPALITY" else 3.0
            if distance <= maximum:
                score += 0.4
            elif distance > maximum * 4:
                return 0.0
        parent_qid = area.get("parent_wikidata_id")
        parent_name = (area.get("parent_name") or area.get("municipality_name") or "").casefold()
        if (
            (parent_qid and parent_qid in candidate.parent_ids)
            or (parent_name and parent_name in description)
            or (
                area["area_type"] == "MUNICIPALITY"
                and any(term in description for term in GEOGRAPHIC_DESCRIPTION_TERMS)
            )
        ):
            score += 0.25
        return round(score, 2)

    @staticmethod
    async def _postgis_distance_km(
        session: AsyncSession | None, area: dict[str, Any], candidate: WikidataEntity
    ) -> float | None:
        if session is None or candidate.latitude is None or candidate.longitude is None:
            return None
        value = await session.scalar(text("""
          SELECT ST_DistanceSphere(
            centroid,
            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)
          ) / 1000.0
          FROM analysis_areas WHERE id=:area_id
        """), {
            "area_id": area["id"], "longitude": candidate.longitude,
            "latitude": candidate.latitude,
        })
        return float(value) if value is not None else None

    async def sync(self, session: AsyncSession, *, force: bool = False) -> WikidataEnrichmentReport:
        stale_before = datetime.now(UTC) - timedelta(days=get_settings().wikidata_stale_days)
        rows = (await session.execute(text("""
          SELECT area.id, area.name, area.area_type, area.source_osm_wikidata,
            area.source_osm_wikipedia, area.wikidata_match_source, area.wikidata_match_status,
            parent.name AS parent_name, parent.wikidata_id AS parent_wikidata_id,
            COALESCE(municipality.name, CASE WHEN area.area_type='MUNICIPALITY' THEN area.name END) AS municipality_name,
            ST_Y(area.centroid) AS latitude, ST_X(area.centroid) AS longitude
          FROM analysis_areas area
          LEFT JOIN analysis_areas parent ON parent.id=area.parent_id
          LEFT JOIN analysis_areas municipality ON municipality.id=CASE
            WHEN area.area_type='DISTRICT' THEN parent.id
            WHEN area.area_type='QUARTER' THEN parent.parent_id END
          WHERE area.wikidata_match_source IS DISTINCT FROM 'MANUAL'
            AND (:force OR area.wikidata_last_checked_at IS NULL
              OR area.wikidata_last_checked_at < :stale_before
              OR area.wikidata_match_status NOT IN ('VERIFIED','AUTO_MATCHED'))
          ORDER BY CASE area.area_type WHEN 'MUNICIPALITY' THEN 1 WHEN 'DISTRICT' THEN 2 ELSE 3 END, area.name
        """), {"force": force, "stale_before": stale_before})).mappings().all()
        report = WikidataEnrichmentReport()
        for row in rows:
            report.checked += 1
            try:
                match = await self.resolve_area(dict(row), session)
                await self.persist_match(session, row["id"], match)
                if match.source == "OSM_WIKIDATA": report.osm_wikidata += 1
                elif match.source == "OSM_WIKIPEDIA": report.osm_wikipedia += 1
                elif match.source == "WIKIDATA_SEARCH": report.search += 1
                elif match.status == "AMBIGUOUS": report.ambiguous += 1
                else: report.not_found += 1
            except Exception as exc:  # noqa: BLE001 - one unavailable entity must not abort bulk
                report.errors.append(f"{row['name']}: {type(exc).__name__}")
        await bump_cache_versions(session, ("analysis-areas",))
        await session.commit()
        return report

    @staticmethod
    async def persist_match(session: AsyncSession, area_id: int, match: Match) -> None:
        entity = match.entity
        await session.execute(text("""
          UPDATE analysis_areas SET
            wikidata_id=:wikidata_id, wikipedia_title=:wikipedia_title,
            wikidata_label=:label, wikidata_description=:description,
            wikidata_match_source=:source, wikidata_match_status=:status,
            wikidata_match_confidence=:confidence, wikidata_last_checked_at=now(),
            wikidata_verified=false, updated_at=now()
          WHERE id=:area_id AND wikidata_match_source IS DISTINCT FROM 'MANUAL'
        """), {
            "area_id": area_id, "wikidata_id": entity.id if entity else None,
            "wikipedia_title": entity.wikipedia_title if entity else None,
            "label": entity.label if entity else None,
            "description": entity.description if entity else None,
            "source": match.source, "status": match.status, "confidence": match.confidence,
        })

    @staticmethod
    async def set_manual_match(session: AsyncSession, area_id: int, qid: str, entity: WikidataEntity) -> None:
        if not QID_RE.fullmatch(qid) or entity.id != qid:
            raise ValueError("Invalid or mismatching Wikidata ID")
        await session.execute(text("""
          UPDATE analysis_areas SET wikidata_id=:qid, wikipedia_title=:title,
            wikidata_label=:label, wikidata_description=:description,
            wikidata_match_source='MANUAL', wikidata_match_status='VERIFIED',
            wikidata_match_confidence=1, wikidata_verified=true,
            wikidata_last_checked_at=now(), updated_at=now() WHERE id=:area_id
        """), {"area_id": area_id, "qid": qid, "title": entity.wikipedia_title,
                 "label": entity.label, "description": entity.description})
        await bump_cache_versions(session, ("analysis-areas",))
        await session.commit()

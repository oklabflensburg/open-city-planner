"""Composition adapters from public module ports to existing Host owners.

Only this boundary knows both the public SDK DTOs and private Host services/models.
The adapters deliberately contain no copied business logic.
"""

import re
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import fields
from urllib.parse import urlsplit

import httpx
from fastapi import Request
from sqlalchemy import any_, false, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import cache_service
from app.core.config import Settings, get_settings
from app.models.user_polygon import UserPolygon
from app.observability.external import instrumented_httpx_request
from app.platform.modules.sdk import (
    AreaStatistics,
    AreaStatisticSeries,
    CachePort,
    CompletenessValue,
    CountValue,
    HttpClientPort,
    HttpResponsePort,
    MapPreviewRequest,
    MapPreviewResult,
    MapPreviewUnavailableError,
    OsmFeatureSnapshotPage,
    OsmSnapshotQuery,
    PolygonFilterValues,
    PolygonIdentity,
    PolygonIdentityRequest,
    PolygonIdentityResult,
    PolygonMetrics,
    PolygonScope,
    PolygonSpatialMatchRequest,
    PolygonSpatialMatchResult,
    PublicPolygonSummary,
    PublicQueryLimits,
    StatisticsArea,
    StatisticSeriesPoint,
    StatisticsSelection,
    StatisticsSource,
    StatisticValue,
)
from app.services import polygon_analytics
from app.services.cache_versions import bump_cache_versions, cache_version
from app.services.map_previews import MapPreviewError, map_preview_service
from app.services.osm_snapshots import list_osm_feature_snapshots
from app.services.polygon_spatial_matches import match_user_polygons
from app.services.public_query_security import (
    guard_public_query,
    is_statement_timeout_error,
)

_MODULE_HTTP_SERVICE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODULE_HTTP_METHODS = frozenset({"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"})
_MODULE_HTTP_TIMEOUT_SECONDS = 10.0


def _module_http_user_agent(settings: Settings) -> str:
    return (
        f"Stadtplaner/{settings.api_version} "
        "(module-http; https://stadtplaner.oklabflensburg.de)"
    )


def _validate_module_http_url(value: str, *, allow_relative: bool) -> None:
    if not value or "\x00" in value:
        raise ValueError("Module HTTP URLs must be non-empty text without NUL bytes.")
    parsed = urlsplit(value)
    if not parsed.scheme and not parsed.netloc:
        if allow_relative:
            return
        raise ValueError("Module HTTP requests require an absolute HTTP(S) URL.")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Module HTTP URLs must use HTTP or HTTPS with a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Module HTTP URLs must not contain credentials.")


class _HostModuleHttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        service_name: str,
        has_base_url: bool,
    ) -> None:
        self._client = client
        self._service_name = service_name
        self._has_base_url = has_base_url

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | None = None,
    ) -> HttpResponsePort:
        _validate_module_http_url(url, allow_relative=self._has_base_url)
        normalized_method = method.upper()
        if normalized_method not in _MODULE_HTTP_METHODS:
            raise ValueError("Module HTTP requests require a supported standard method.")
        request_kwargs: dict[str, object] = {}
        if headers is not None:
            request_kwargs["headers"] = dict(headers)
        if params is not None:
            request_kwargs["params"] = params
        if content is not None:
            request_kwargs["content"] = content
        return await instrumented_httpx_request(
            self._client,
            normalized_method,
            url,
            provider=self._service_name,
            operation=normalized_method,
            **request_kwargs,
        )


class HostModuleHttpClientFactory:
    """Bounded, observable HTTP clients for trusted in-process modules."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._user_agent = _module_http_user_agent(settings or get_settings())
        self._transport = transport

    @asynccontextmanager
    async def create(
        self,
        *,
        service_name: str,
        base_url: str | None = None,
    ) -> AsyncIterator[HttpClientPort]:
        if not _MODULE_HTTP_SERVICE_NAME.fullmatch(service_name):
            raise ValueError(
                "Module HTTP service names must use 1-64 lowercase letters, digits, dots, "
                "underscores, or hyphens."
            )
        if base_url is not None:
            _validate_module_http_url(base_url, allow_relative=False)
        async with httpx.AsyncClient(
            base_url=base_url or "",
            timeout=httpx.Timeout(_MODULE_HTTP_TIMEOUT_SECONDS),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={"User-Agent": self._user_agent},
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        ) as client:
            yield _HostModuleHttpClient(
                client,
                service_name=service_name,
                has_base_url=base_url is not None,
            )


class HostModuleCache(CachePort):
    """Redis-backed byte cache scoped to exactly one module ID."""

    def __init__(self, module_id: str) -> None:
        cache_prefix = get_settings().cache_prefix.strip(":")
        self._prefix = f"{cache_prefix}:module:{module_id}:"

    def _key(self, key: str) -> str:
        if not key or "\0" in key:
            raise ValueError("Module cache keys must be non-empty text without NUL bytes.")
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> bytes | None:
        return await cache_service.get(self._key(key))

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> bool:
        if type(ttl_seconds) is not int or ttl_seconds < 1:
            raise ValueError("Module cache TTLs must be positive integer seconds.")
        return await cache_service.set(self._key(key), value, ttl_seconds)

    async def delete(self, *keys: str) -> int:
        return await cache_service.delete(*(self._key(key) for key in keys))

    async def clear(self) -> int:
        return await cache_service.delete_pattern(f"{self._prefix}*")


class HostCacheGenerations:
    """Adapter for shared read-model invalidation generations."""

    async def current(self, session: AsyncSession, resource: str) -> int:
        return await cache_version(session, resource)

    async def bump(
        self, session: AsyncSession, resources: Sequence[str]
    ) -> None:
        await bump_cache_versions(session, resources)


class HostPublicQueries:
    """Adapter for the existing public-query security policy."""

    def __init__(self, settings: Settings | None = None) -> None:
        active = settings or get_settings()
        self._limits = PublicQueryLimits(
            max_response_items=active.public_polygon_response_limit,
            cache_debug_headers=active.cache_debug_headers,
        )

    @property
    def limits(self) -> PublicQueryLimits:
        return self._limits

    async def guard(
        self, request: Request, session: AsyncSession, resource: str
    ) -> None:
        await guard_public_query(request, session, resource)

    def is_timeout(self, error: BaseException) -> bool:
        return is_statement_timeout_error(error)


class HostOsmSnapshotQueries:
    """Public, immutable projections of the Host-owned OSM snapshot."""

    async def list_features(
        self, session: AsyncSession, query: OsmSnapshotQuery
    ) -> OsmFeatureSnapshotPage:
        return await list_osm_feature_snapshots(session, query)


class HostMapPreviews:
    """Adapter for the existing native map-preview service."""

    async def render(self, request: MapPreviewRequest) -> MapPreviewResult:
        try:
            preview = await map_preview_service.get(
                slug=request.slug,
                updated_at=request.updated_at,
                geometry=dict(request.geometry),
                bbox=request.bbox,
                width=request.width,
                height=request.height,
                category=request.category,
                feature_kind=request.feature_kind,
            )
        except MapPreviewError as exc:
            raise MapPreviewUnavailableError(str(exc)) from exc
        return MapPreviewResult(
            body=preview.body,
            content_type="image/webp",
            etag=preview.etag,
            cache_hit=preview.cache_hit,
        )


def _polygon_scope_filter(scope: PolygonScope):
    if not scope.polygon_ids:
        return false()
    return UserPolygon.id == any_(scope.polygon_ids)


def _polygon_filters(scope: PolygonScope, values: PolygonFilterValues):
    result = polygon_analytics.base_filters(
        values.floors,
        values.area_sizes,
        values.occupancy_statuses,
        values.business_structures,
        values.sources,
    )
    result.append(_polygon_scope_filter(scope))
    if values.categories:
        result.append(UserPolygon.category.in_(values.categories))
    return result


class HostPolygonQueries:
    """Public read projections owned by the polygon domain."""

    async def list_by_scope(
        self, session: AsyncSession, scope: PolygonScope, *, limit: int
    ) -> tuple[PublicPolygonSummary, ...]:
        if type(limit) is not int or limit < 1:
            raise ValueError("Polygon query limits must be positive integer values.")
        area_m2 = func.ST_Area(func.ST_Transform(UserPolygon.geometry, 25832))
        rows = (
            await session.execute(
                select(
                    UserPolygon.uuid,
                    UserPolygon.slug,
                    UserPolygon.name,
                    UserPolygon.category,
                    UserPolygon.floor,
                    UserPolygon.address_display_name,
                    UserPolygon.occupancy_status,
                    area_m2.label("area_m2"),
                )
                .where(_polygon_scope_filter(scope))
                .order_by(UserPolygon.updated_at.desc(), UserPolygon.id.desc())
                .limit(limit)
            )
        ).mappings()
        return tuple(
            PublicPolygonSummary(
                id=str(row["uuid"]),
                slug=row["slug"],
                name=row["name"],
                category=row["category"],
                floor=row["floor"],
                address_display_name=row["address_display_name"],
                occupancy_status=row["occupancy_status"] or "UNKNOWN",
                area_m2=float(row["area_m2"]) if row["area_m2"] is not None else None,
            )
            for row in rows
        )


class HostPolygonSpatialMatches:
    """Delegates read-only spatial matching to the polygon-owned query service."""

    async def match_polygons(
        self, session: AsyncSession, request: PolygonSpatialMatchRequest
    ) -> PolygonSpatialMatchResult:
        return await match_user_polygons(session, request)


class HostPolygonIdentities:
    """Resolves stable public UUIDs without exposing the Host polygon model."""

    async def resolve(
        self, session: AsyncSession, request: PolygonIdentityRequest
    ) -> PolygonIdentityResult:
        if not request.polygon_uuids:
            return PolygonIdentityResult((), ())
        rows = (
            await session.execute(
                select(UserPolygon.id, UserPolygon.uuid).where(
                    UserPolygon.uuid == any_(request.polygon_uuids)
                )
            )
        ).all()
        identities = {row.uuid: PolygonIdentity(id=row.id, uuid=row.uuid) for row in rows}
        return PolygonIdentityResult(
            resolved=tuple(
                identities[value] for value in request.polygon_uuids if value in identities
            ),
            missing=tuple(value for value in request.polygon_uuids if value not in identities),
        )


def _count_values(values) -> tuple[CountValue, ...]:
    return tuple(
        CountValue(
            key=getattr(value, "key", getattr(value, "category", "")),
            label=getattr(value, "label", None),
            count=value.count,
        )
        for value in values
    )


class HostPolygonAnalytics:
    """Public aggregate adapter owned by polygon analytics."""

    async def metrics(
        self,
        session: AsyncSession,
        scope: PolygonScope,
        filters: PolygonFilterValues,
    ) -> PolygonMetrics:
        result = await polygon_analytics.benchmark_metrics(
            session, _polygon_filters(scope, filters)
        )
        return PolygonMetrics(
            **{
                field.name: getattr(result, field.name)
                for field in fields(PolygonMetrics)
                if field.name
                not in {
                    "size_distribution",
                    "floor_distribution",
                    "status_distribution",
                    "business_structure_distribution",
                    "data_completeness",
                }
            },
            size_distribution=_count_values(result.size_distribution),
            floor_distribution=_count_values(result.floor_distribution),
            status_distribution=_count_values(result.status_distribution),
            business_structure_distribution=_count_values(
                result.business_structure_distribution
            ),
            data_completeness=tuple(
                CompletenessValue(**item.model_dump()) for item in result.data_completeness
            ),
        )

    async def category_counts(
        self,
        session: AsyncSession,
        scope: PolygonScope,
        filters: PolygonFilterValues,
    ) -> tuple[CountValue, ...]:
        values = await polygon_analytics.counts(
            session, _polygon_filters(scope, filters)
        )
        return _count_values(values)


def _statistics_area(value: StatisticsArea) -> StatisticsArea:
    return StatisticsArea(
        id=value.id,
        slug=value.slug,
        name=value.name,
        area_type=value.area_type,
    )


async def _statistics_mapping(
    session: AsyncSession, selection: StatisticsSelection
) -> Mapping[str, object] | None:
    return (
        await session.execute(
            text("""
              SELECT target.id AS target_id,
                     municipality.id AS municipality_id,
                     target.source AS source
              FROM external_area_mappings target
              JOIN external_area_mappings municipality
                ON municipality.source=target.source
              WHERE target.external_area_name=:target_name
                AND target.level=:target_level
                AND municipality.external_area_name=:municipality_name
                AND municipality.level=:municipality_level
              ORDER BY target.source
              LIMIT 1
            """),
            {
                "target_name": selection.target.name,
                "target_level": selection.target.area_type,
                "municipality_name": selection.municipality.name,
                "municipality_level": selection.municipality.area_type,
            },
        )
    ).mappings().first()


async def _statistics_source(
    session: AsyncSession, source: str
) -> StatisticsSource | None:
    row = (
        await session.execute(
            text("""
              SELECT name,source_url,license,last_import_at,source_updated_at
              FROM statistical_datasets
              WHERE source=:source AND last_import_at IS NOT NULL
              ORDER BY last_import_at DESC,id DESC
              LIMIT 1
            """),
            {"source": source},
        )
    ).mappings().first()
    if row is None:
        return None
    return StatisticsSource(
        name=str(row["name"]),
        url=str(row["source_url"]),
        license=str(row["license"]),
        source_updated_at=row["source_updated_at"],
        last_import_at=row["last_import_at"],
    )


class HostStatisticsQueries:
    """Read-only compatibility projection over preserved statistical data.

    Import, scheduling, APIs and domain policy belong to modules. This adapter
    only fulfills the published SDK port while the historical tables remain in
    the Host migration lineage.
    """

    async def for_selection(
        self, session: AsyncSession, selection: StatisticsSelection
    ) -> AreaStatistics | None:
        mapping = await _statistics_mapping(session, selection)
        if mapping is None:
            return None
        rows = (
            await session.execute(
                text("""
                  WITH ranked AS (
                    SELECT observation.*,row_number() OVER (
                      PARTITION BY observation.metric_id
                      ORDER BY observation.period_start DESC
                    ) AS rank
                    FROM statistical_observations observation
                    WHERE observation.statistical_area_id=:target_id
                  )
                  SELECT metric.key,metric.name,metric.category,metric.unit,
                         ranked.value_numeric,ranked.period_start,ranked.is_calculated,
                         municipality.value_numeric AS municipality_value
                  FROM ranked
                  JOIN statistical_metrics metric ON metric.id=ranked.metric_id
                  JOIN statistical_datasets dataset ON dataset.id=metric.dataset_id
                  LEFT JOIN statistical_observations municipality
                    ON municipality.metric_id=ranked.metric_id
                   AND municipality.statistical_area_id=:municipality_id
                   AND municipality.period_start=ranked.period_start
                  WHERE ranked.rank=1 AND metric.public=true AND dataset.source=:source
                  ORDER BY metric.category,metric.name
                """),
                mapping,
            )
        ).mappings().all()
        latest = []
        for row in rows:
            value = row["value_numeric"]
            municipality_value = row["municipality_value"]
            difference = (
                value - municipality_value
                if value is not None and municipality_value is not None
                else None
            )
            relative_difference = (
                difference / municipality_value * 100
                if difference is not None and municipality_value
                else None
            )
            latest.append(
                StatisticValue(
                    key=str(row["key"]),
                    name=str(row["name"]),
                    category=str(row["category"]),
                    value=value,
                    unit=str(row["unit"]),
                    period=str(row["period_start"].year),
                    period_start=row["period_start"],
                    area_level=selection.target.area_type,
                    is_calculated=bool(row["is_calculated"]),
                    municipality_value=municipality_value,
                    difference=difference,
                    relative_difference=relative_difference,
                )
            )
        return AreaStatistics(
            area=_statistics_area(selection.requested),
            statistics_area=_statistics_area(selection.target),
            inherited_from_parent=selection.inherited,
            source=await _statistics_source(session, str(mapping["source"])),
            latest=tuple(latest),
        )

    async def series_for_selection(
        self,
        session: AsyncSession,
        selection: StatisticsSelection,
        metric_key: str,
    ) -> AreaStatisticSeries | None:
        mapping = await _statistics_mapping(session, selection)
        if mapping is None:
            return None
        metric = (
            await session.execute(
                text("""
                  SELECT metric.id,metric.key,metric.name,metric.unit,metric.category
                  FROM statistical_metrics metric
                  JOIN statistical_datasets dataset ON dataset.id=metric.dataset_id
                  WHERE metric.key=:metric_key AND metric.public=true
                    AND dataset.source=:source
                  LIMIT 1
                """),
                {**mapping, "metric_key": metric_key},
            )
        ).mappings().first()
        if metric is None:
            return None
        rows = (
            await session.execute(
                text("""
                  SELECT period_start,value_numeric,value_text
                  FROM statistical_observations
                  WHERE metric_id=:metric_id AND statistical_area_id=:target_id
                  ORDER BY period_start
                """),
                {"metric_id": metric["id"], "target_id": mapping["target_id"]},
            )
        ).mappings().all()
        return AreaStatisticSeries(
            area=_statistics_area(selection.requested),
            statistics_area=_statistics_area(selection.target),
            inherited_from_parent=selection.inherited,
            source=await _statistics_source(session, str(mapping["source"])),
            metric={key: str(metric[key]) for key in ("key", "name", "unit", "category")},
            series=tuple(
                StatisticSeriesPoint(
                    period=str(row["period_start"].year),
                    period_start=row["period_start"],
                    value=row["value_numeric"],
                    suppressed=row["value_text"] == "suppressed",
                )
                for row in rows
            ),
        )


__all__ = [
    "HostCacheGenerations",
    "HostMapPreviews",
    "HostModuleCache",
    "HostOsmSnapshotQueries",
    "HostPolygonAnalytics",
    "HostPolygonIdentities",
    "HostPolygonQueries",
    "HostPolygonSpatialMatches",
    "HostPublicQueries",
    "HostStatisticsQueries",
]

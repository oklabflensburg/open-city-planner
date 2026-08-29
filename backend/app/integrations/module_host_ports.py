"""Composition adapters from public module ports to existing Host owners.

Only this boundary knows both the public SDK DTOs and private Host services/models.
The adapters deliberately contain no copied business logic.
"""

from dataclasses import fields
from typing import cast

from fastapi import Request
from sqlalchemy import any_, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import cache_service
from app.core.config import Settings, get_settings
from app.models.user_polygon import UserPolygon
from app.platform.modules.sdk import (
    AreaStatistics,
    AreaStatisticSeries,
    CachePort,
    CompletenessValue,
    CountValue,
    MapPreviewRequest,
    MapPreviewResult,
    MapPreviewUnavailableError,
    PolygonFilterValues,
    PolygonMetrics,
    PolygonScope,
    PublicPolygonSummary,
    PublicQueryLimits,
    StatisticsArea,
    StatisticSeriesPoint,
    StatisticsSource,
    StatisticValue,
)
from app.services import polygon_analytics
from app.services.cache_versions import cache_version
from app.services.map_previews import MapPreviewError, map_preview_service
from app.services.public_query_security import (
    guard_public_query,
    is_statement_timeout_error,
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


def _statistics_area(value) -> StatisticsArea:
    return StatisticsArea(
        id=value.id,
        slug=value.slug,
        name=value.name,
        area_type=value.area_type,
    )


def _statistics_source(value) -> StatisticsSource | None:
    if value is None:
        return None
    return StatisticsSource(
        name=value.name,
        url=value.url,
        license=value.license,
        source_updated_at=value.source_updated_at,
        last_import_at=value.last_import_at,
    )


class HostStatisticsQueries:
    """Public DTO adapter owned by the municipal-statistics domain."""

    async def for_area(self, session: AsyncSession, slug: str) -> AreaStatistics | None:
        from app.services import area_statistics

        value = await area_statistics.area_statistics(session, slug)
        if value is None:
            return None
        return AreaStatistics(
            area=_statistics_area(value.area),
            statistics_area=_statistics_area(value.statistics_area),
            inherited_from_parent=value.inherited_from_parent,
            source=_statistics_source(value.source),
            latest=tuple(StatisticValue(**item.model_dump()) for item in value.latest),
        )

    async def series_for_area(
        self, session: AsyncSession, slug: str, metric_key: str
    ) -> AreaStatisticSeries | None:
        from app.services import area_statistics

        value = await area_statistics.area_statistic_series(session, slug, metric_key)
        if value is None:
            return None
        return AreaStatisticSeries(
            area=_statistics_area(value.area),
            statistics_area=_statistics_area(value.statistics_area),
            inherited_from_parent=value.inherited_from_parent,
            source=_statistics_source(value.source),
            metric=cast(dict[str, str], value.metric),
            series=tuple(
                StatisticSeriesPoint(**item.model_dump()) for item in value.series
            ),
        )


__all__ = [
    "HostCacheGenerations",
    "HostMapPreviews",
    "HostModuleCache",
    "HostPolygonAnalytics",
    "HostPolygonQueries",
    "HostPublicQueries",
    "HostStatisticsQueries",
]

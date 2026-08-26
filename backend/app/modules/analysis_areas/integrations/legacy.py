"""Temporary host/domain adapters for #107; remove through #108/#128/#129.

The module owns the compatibility URLs while Statistics, Polygons, map preview,
cache and public-query security retain their existing ownership. Keeping every
private import in this one exact adapter makes the strangler boundary auditable.
"""

from app.cache import keys as cache_keys
from app.cache import service as cache_service_module
from app.core.config import get_settings
from app.db.session import get_session
from app.models.user_polygon import UserPolygon
from app.schemas import analytics, external_links, geojson, polygon_filters, statistics
from app.services import (
    analytics as analytics_service,
)
from app.services import (
    area_statistics as statistics_service,
)
from app.services import (
    cache_versions,
    map_previews,
    poi_categories,
    public_query_security,
    social_publishing,
)

AreaStatisticSeriesRead = statistics.AreaStatisticSeriesRead
AreaStatisticsRead = statistics.AreaStatisticsRead
BenchmarkMetrics = analytics.BenchmarkMetrics
IndustryCount = analytics.IndustryCount
ExternalLinks = external_links.ExternalLinks
WikidataExternalLink = external_links.WikidataExternalLink
WikipediaExternalLink = external_links.WikipediaExternalLink
AreaGeometry = geojson.AreaGeometry
PolygonFilterParams = polygon_filters.PolygonFilterParams
polygon_filter_query = polygon_filters.polygon_filter_query
build_cache_key = cache_keys.build_cache_key
cache_service = cache_service_module.cache_service
last_cache_status = cache_service_module.last_cache_status
area_statistic_series = statistics_service.area_statistic_series
area_statistics = statistics_service.area_statistics
MapPreviewError = map_previews.MapPreviewError
map_preview_service = map_previews.map_preview_service
guard_public_query = public_query_security.guard_public_query
is_statement_timeout_error = public_query_security.is_statement_timeout_error
base_filters = analytics_service._base_filters
benchmark_metrics = analytics_service._benchmark_metrics
counts = analytics_service._counts
cache_version = cache_versions.cache_version
bump_cache_versions = cache_versions.bump_cache_versions
AREA_POI_CATEGORY_SQL = poi_categories.AREA_POI_CATEGORY_SQL
enqueue_area_publication = social_publishing.enqueue_area_publication

__all__ = [
    "AREA_POI_CATEGORY_SQL",
    "AreaGeometry",
    "AreaStatisticSeriesRead",
    "AreaStatisticsRead",
    "BenchmarkMetrics",
    "ExternalLinks",
    "IndustryCount",
    "MapPreviewError",
    "PolygonFilterParams",
    "UserPolygon",
    "WikidataExternalLink",
    "WikipediaExternalLink",
    "area_statistic_series",
    "area_statistics",
    "base_filters",
    "benchmark_metrics",
    "build_cache_key",
    "bump_cache_versions",
    "cache_service",
    "cache_version",
    "counts",
    "enqueue_area_publication",
    "get_session",
    "get_settings",
    "guard_public_query",
    "is_statement_timeout_error",
    "last_cache_status",
    "map_preview_service",
    "polygon_filter_query",
]

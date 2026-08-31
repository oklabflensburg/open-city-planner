import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key
from app.cache.service import cache_service
from app.core.config import get_settings
from app.models.user_polygon import UserPolygon
from app.schemas.analytics import (
    AnalyticsFastFacts,
    AnalyticsOverview,
    AreaCompareFilters,
    AreaCompareItem,
    AreaCompareMetrics,
    AreaCompareRequest,
    AreaCompareResult,
    MarketBenchmark,
    MarketBenchmarkResult,
    PrimeRentData,
)
from app.schemas.polygon_filters import PolygonFilterParams
from app.services.cache_versions import cache_version
from app.services.city_metrics import get_public_city_metrics
from app.services.polygon_analytics import base_filters as _polygon_base_filters
from app.services.polygon_analytics import (
    benchmark_metrics as _benchmark_metrics,
)
from app.services.polygon_analytics import counts as _counts
from app.services.polygon_filters import polygon_filter_clauses

# A shop is currently a public polygon assigned to one of the maintained retail/service
# categories. "otherAreas" and unknown/custom categories are deliberately excluded.
SHOP_CATEGORIES = (
    "warehouse",
    "fashion",
    "food",
    "electronics",
    "furniture",
    "garden",
    "other",
    "gastronomy",
    "services",
)

# Explicit, read-only neighboring-domain table contract. Ownership of both
# tables and their ORM mappings remains with the external Analysis Areas module.
_AREAS = table(
    "analysis_areas",
    column("id"),
    column("uuid"),
    column("slug"),
    column("name"),
    column("area_type"),
    column("parent_id"),
    column("area_m2"),
    column("geometry"),
    column("centroid"),
)
_POLYGON_AREAS = table(
    "polygon_analysis_areas",
    column("polygon_id"),
    column("analysis_area_id"),
)


@dataclass(frozen=True, slots=True)
class AreaAnalyticsScope:
    id: int
    uuid: uuid.UUID
    slug: str
    name: str
    area_type: str
    parent_id: int | None
    area_m2: float
    geometry: object
    centroid: object


def _area_scope(row) -> AreaAnalyticsScope:
    return AreaAnalyticsScope(**{field: row[field] for field in AreaAnalyticsScope.__slots__})


def _area_columns(source=_AREAS):
    return tuple(source.c[name] for name in AreaAnalyticsScope.__slots__)


def _base_filters(
    floors: Sequence[str],
    area_sizes: Sequence[str],
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
    analysis_area_id: int | None = None,
) -> list[object]:
    filters = _polygon_base_filters(
        floors, area_sizes, occupancy_statuses, business_structures, sources
    )
    if analysis_area_id is not None:
        filters.append(UserPolygon.id.in_(
            select(_POLYGON_AREAS.c.polygon_id).where(
                _POLYGON_AREAS.c.analysis_area_id == analysis_area_id
            )
        ))
    return filters


async def _resolve_area(
    session: AsyncSession, area_id: uuid.UUID | None
) -> AreaAnalyticsScope | None:
    if area_id is None:
        return None
    row = (
        await session.execute(select(*_area_columns()).where(_AREAS.c.uuid == area_id))
    ).mappings().one_or_none()
    return _area_scope(row) if row is not None else None


async def _analytics_overview_uncached(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
    area_id: uuid.UUID | None = None,
) -> AnalyticsOverview:
    area = await _resolve_area(session, area_id)
    filter_params = PolygonFilterParams(
        categories=tuple(categories), floors=tuple(floors), area_sizes=tuple(area_sizes),
        occupancy_statuses=tuple(occupancy_statuses), business_structures=tuple(business_structures),
        sources=tuple(sources),
    )
    base_filters = polygon_filter_clauses(filter_params, exclude={"categories"})
    if area:
        base_filters.append(UserPolygon.id.in_(
            select(_POLYGON_AREAS.c.polygon_id).where(
                _POLYGON_AREAS.c.analysis_area_id == area.id
            )
        ))
    category_counts = await _counts(session, base_filters)

    selected_filters = polygon_filter_clauses(filter_params)
    if area:
        selected_filters.append(UserPolygon.id.in_(
            select(_POLYGON_AREAS.c.polygon_id).where(
                _POLYGON_AREAS.c.analysis_area_id == area.id
            )
        ))
    distribution = await _counts(session, selected_filters)

    shops = sum(
        item.count for item in distribution if item.category in SHOP_CATEGORIES
    )
    calculated = await _benchmark_metrics(session, selected_filters)
    city_metrics = await get_public_city_metrics(session)

    return AnalyticsOverview(
        fast_facts=AnalyticsFastFacts(
            shops=shops,
            polygon_count=calculated.polygon_count,
            total_area_m2=calculated.total_area_m2,
            average_area_m2=calculated.average_area_m2,
            median_area_m2=calculated.median_area_m2,
            vacant_area_m2=calculated.vacant_area_m2,
            vacancy_area_rate=calculated.vacancy_area_rate,
            calculated_vacancy_rate=calculated.vacancy_rate,
            calculated_chain_store_rate=calculated.chain_store_rate,
            known_occupancy_count=calculated.known_occupancy_count,
            known_business_structure_count=calculated.known_business_structure_count,
            data_updated_at=calculated.data_updated_at,
            **city_metrics.model_dump(),
        ),
        industry_distribution=distribution,
        category_counts=category_counts,
        size_distribution=calculated.size_distribution,
        floor_distribution=calculated.floor_distribution,
        status_distribution=calculated.status_distribution,
        business_structure_distribution=calculated.business_structure_distribution,
        data_completeness=calculated.data_completeness,
        # price_per_sqm is an internal management field, not a public rent dataset.
        prime_rents=PrimeRentData(),
    )


async def analytics_overview(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
    area_id: uuid.UUID | None = None,
) -> AnalyticsOverview:
    params = {
        "area_id": area_id,
        "categories": categories,
        "floors": floors,
        "area_sizes": area_sizes,
        "occupancy_statuses": occupancy_statuses,
        "business_structures": business_structures,
        "sources": sources,
        "scope": "public",
    }
    version = await cache_version(session, "analytics")
    key = build_cache_key("analytics:overview", params, version=version)

    async def valid_compute() -> dict:
        result = await _analytics_overview_uncached(
            session,
            categories=categories,
            floors=floors,
            area_sizes=area_sizes,
            occupancy_statuses=occupancy_statuses,
            business_structures=business_structures,
            sources=sources,
            area_id=area_id,
        )
        return result.model_dump(mode="json")

    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().analytics_cache_ttl,
        resource="analytics-overview",
        compute=valid_compute,
    )
    return AnalyticsOverview.model_validate(data)


async def _market_benchmarks_uncached(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
    area_id: uuid.UUID | None = None,
) -> MarketBenchmarkResult:
    area = await _resolve_area(session, area_id)
    selected_filters = _base_filters(
        floors, area_sizes, occupancy_statuses, business_structures, sources,
        area.id if area else None,
    )
    if categories:
        selected_filters.append(UserPolygon.category.in_(categories))
    selected = await _benchmark_metrics(session, selected_filters)
    municipality = None
    if area is not None:
        if area.area_type == "MUNICIPALITY":
            municipality = area
        else:
            row = (
                await session.execute(
                    select(*_area_columns())
                    .where(
                        _AREAS.c.area_type == "MUNICIPALITY",
                        func.ST_Covers(_AREAS.c.geometry, area.centroid),
                    )
                    .limit(1)
                )
            ).mappings().one_or_none()
            municipality = _area_scope(row) if row is not None else None
    city_filters = _base_filters(
        floors, area_sizes, occupancy_statuses, business_structures, sources,
        municipality.id if municipality else None,
    )
    if categories:
        city_filters.append(UserPolygon.category.in_(categories))
    city = await _benchmark_metrics(session, city_filters)
    return MarketBenchmarkResult(
        context_label=(f"{area.name} im Vergleich zur Gesamtstadt" if area else "Aktuelle Filterauswahl im Vergleich zur Gesamtstadt"),
        items=[
            MarketBenchmark(key="selection", label="Aktuelle Auswahl", metrics=selected),
            MarketBenchmark(key="city", label="Gesamtstadt", metrics=city),
        ],
    )


async def market_benchmarks(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
    area_id: uuid.UUID | None = None,
) -> MarketBenchmarkResult:
    params = {
        "area_id": area_id,
        "categories": categories,
        "floors": floors,
        "area_sizes": area_sizes,
        "occupancy_statuses": occupancy_statuses,
        "business_structures": business_structures,
        "sources": sources,
        "scope": "public",
    }
    version = await cache_version(session, "analytics")
    key = build_cache_key("analytics:benchmarks", params, version=version)

    async def compute() -> dict:
        result = await _market_benchmarks_uncached(
            session,
            categories=categories,
            floors=floors,
            area_sizes=area_sizes,
            occupancy_statuses=occupancy_statuses,
            business_structures=business_structures,
            sources=sources,
            area_id=area_id,
        )
        return result.model_dump(mode="json")

    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().analytics_cache_ttl,
        resource="analytics-benchmarks",
        compute=compute,
    )
    return MarketBenchmarkResult.model_validate(data)


def _compare_filter_params(filters: AreaCompareFilters) -> PolygonFilterParams:
    return PolygonFilterParams(
        categories=tuple(filters.categories),
        floors=tuple(filters.floors),
        area_sizes=tuple(filters.area_sizes),
        occupancy_statuses=tuple(filters.occupancy_statuses),
        business_structures=tuple(filters.business_structures),
        sources=tuple(filters.sources),
    )


async def _compare_metrics_by_area(
    session: AsyncSession,
    area_ids: Sequence[int],
    filters: AreaCompareFilters,
) -> dict[int, AreaCompareMetrics]:
    if not area_ids:
        return {}
    area = func.ST_Area(func.ST_Transform(UserPolygon.geometry, 25832))
    clauses = polygon_filter_clauses(_compare_filter_params(filters))
    statement = (
        select(
            _POLYGON_AREAS.c.analysis_area_id.label("analysis_area_id"),
            func.count(UserPolygon.id).label("polygon_count"),
            func.sum(area).label("total_area_m2"),
            func.avg(area).label("average_area_m2"),
            func.percentile_cont(0.5).within_group(area).label("median_area_m2"),
            func.count(UserPolygon.id).filter(UserPolygon.occupancy_status == "OCCUPIED").label("occupied_count"),
            func.count(UserPolygon.id).filter(UserPolygon.occupancy_status == "VACANT").label("vacant_count"),
            func.count(UserPolygon.id).filter(UserPolygon.occupancy_status != "UNKNOWN").label("known_occupancy_count"),
            func.count(UserPolygon.id).filter(UserPolygon.business_structure == "CHAIN").label("chain_count"),
            func.count(UserPolygon.id).filter(UserPolygon.business_structure == "INDEPENDENT").label("independent_count"),
            func.count(UserPolygon.id).filter(UserPolygon.business_structure != "UNKNOWN").label("known_business_count"),
            func.max(UserPolygon.updated_at).label("data_updated_at"),
        )
        .select_from(_POLYGON_AREAS)
        .join(UserPolygon, UserPolygon.id == _POLYGON_AREAS.c.polygon_id)
        .where(_POLYGON_AREAS.c.analysis_area_id.in_(area_ids), *clauses)
        .group_by(_POLYGON_AREAS.c.analysis_area_id)
    )
    rows = (await session.execute(statement)).mappings().all()
    result: dict[int, AreaCompareMetrics] = {}
    for row in rows:
        known_occupancy = int(row["known_occupancy_count"] or 0)
        known_business = int(row["known_business_count"] or 0)
        vacant = int(row["vacant_count"] or 0)
        chains = int(row["chain_count"] or 0)
        result[int(row["analysis_area_id"])] = AreaCompareMetrics(
            polygon_count=int(row["polygon_count"] or 0),
            occupied_count=int(row["occupied_count"] or 0),
            vacant_count=vacant,
            chain_count=chains,
            independent_count=int(row["independent_count"] or 0),
            total_area_m2=float(row["total_area_m2"]) if row["total_area_m2"] is not None else None,
            average_area_m2=float(row["average_area_m2"]) if row["average_area_m2"] is not None else None,
            median_area_m2=float(row["median_area_m2"]) if row["median_area_m2"] is not None else None,
            vacancy_rate=round(vacant / known_occupancy * 100, 2) if known_occupancy else None,
            chain_store_rate=round(chains / known_business * 100, 2) if known_business else None,
            known_occupancy_count=known_occupancy,
            known_business_structure_count=known_business,
            data_updated_at=row["data_updated_at"],
        )
    return result


def _compare_item(
    area: AreaAnalyticsScope,
    parent_name: str | None,
    metrics: AreaCompareMetrics | None,
) -> AreaCompareItem:
    values = metrics or AreaCompareMetrics()
    area_km2 = area.area_m2 / 1_000_000 if area.area_m2 else 0
    if area_km2:
        values = values.model_copy(update={
            "locations_per_km2": round(values.polygon_count / area_km2, 2),
            "retail_area_m2_per_km2": (
                round(values.total_area_m2 / area_km2, 2)
                if values.total_area_m2 is not None else None
            ),
        })
    return AreaCompareItem(
        id=str(area.uuid), slug=area.slug, name=area.name, area_type=area.area_type,
        parent_name=parent_name, area_m2=area.area_m2, metrics=values,
    )


async def _compare_areas_uncached(
    session: AsyncSession,
    request: AreaCompareRequest,
) -> AreaCompareResult:
    parent = _AREAS.alias("parent_analysis_area")
    rows = (
        await session.execute(
            select(*_area_columns(), parent.c.name.label("parent_name"))
            .select_from(_AREAS.outerjoin(parent, parent.c.id == _AREAS.c.parent_id))
            .where(_AREAS.c.slug.in_(request.area_slugs))
        )
    ).mappings().all()
    found = {
        row["slug"]: (_area_scope(row), row["parent_name"])
        for row in rows
    }
    selected = [found[slug] for slug in request.area_slugs if slug in found]
    ignored = [slug for slug in request.area_slugs if slug not in found]

    municipality: AreaAnalyticsScope | None = None
    municipality_parent_name: str | None = None
    if request.include_municipality_benchmark and selected:
        municipality_pair = next((pair for pair in selected if pair[0].area_type == "MUNICIPALITY"), None)
        if municipality_pair:
            municipality, municipality_parent_name = municipality_pair
        else:
            row = (
                await session.execute(
                    select(*_area_columns())
                    .where(
                        _AREAS.c.area_type == "MUNICIPALITY",
                        func.ST_Covers(_AREAS.c.geometry, selected[0][0].centroid),
                    )
                    .limit(1)
                )
            ).mappings().one_or_none()
            municipality = _area_scope(row) if row is not None else None

    metric_areas = [area for area, _parent_name in selected]
    if municipality and all(area.id != municipality.id for area in metric_areas):
        metric_areas.append(municipality)
    metrics = await _compare_metrics_by_area(
        session, [area.id for area in metric_areas], request.filters
    )
    items = [_compare_item(area, parent_name, metrics.get(area.id)) for area, parent_name in selected]
    benchmark = None
    if municipality and all(area.id != municipality.id for area, _parent_name in selected):
        benchmark = _compare_item(municipality, municipality_parent_name, metrics.get(municipality.id))
    return AreaCompareResult(areas=items, benchmark=benchmark, ignored_slugs=ignored)


async def compare_areas(session: AsyncSession, request: AreaCompareRequest) -> AreaCompareResult:
    analytics_version = await cache_version(session, "analytics")
    area_version = await cache_version(session, "analysis-areas")
    key = build_cache_key(
        "analytics:compare",
        request.model_dump(mode="json"),
        version=f"{analytics_version}:{area_version}",
    )

    async def compute() -> dict:
        result = await _compare_areas_uncached(session, request)
        return result.model_dump(mode="json")

    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().analytics_cache_ttl,
        resource="analytics-compare",
        compute=compute,
    )
    return AreaCompareResult.model_validate(data)

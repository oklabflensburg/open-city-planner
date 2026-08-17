import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key
from app.cache.service import cache_service
from app.core.config import get_settings
from app.models.analysis_area import AnalysisArea, PolygonAnalysisArea
from app.models.user_polygon import UserPolygon
from app.schemas.analytics import (
    AnalyticsFastFacts,
    AnalyticsOverview,
    BenchmarkMetrics,
    CompletenessMetric,
    DimensionCount,
    IndustryCount,
    MarketBenchmark,
    MarketBenchmarkResult,
    PrimeRentData,
)
from app.schemas.polygon_filters import PolygonFilterParams
from app.services.cache_versions import cache_version
from app.services.city_metrics import get_public_city_metrics
from app.services.polygon_filters import floor_group_expression, polygon_filter_clauses

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


def _base_filters(
    floors: Sequence[str],
    area_sizes: Sequence[str],
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
    analysis_area_id: int | None = None,
) -> list[object]:
    filters = polygon_filter_clauses(PolygonFilterParams(
        floors=tuple(floors),
        area_sizes=tuple(area_sizes),
        occupancy_statuses=tuple(occupancy_statuses),
        business_structures=tuple(business_structures),
        sources=tuple(sources),
    ))
    if analysis_area_id is not None:
        filters.append(UserPolygon.id.in_(
            select(PolygonAnalysisArea.polygon_id).where(PolygonAnalysisArea.analysis_area_id == analysis_area_id)
        ))
    return filters


async def _resolve_area(session: AsyncSession, area_id: uuid.UUID | None) -> AnalysisArea | None:
    if area_id is None:
        return None
    return await session.scalar(select(AnalysisArea).where(AnalysisArea.uuid == area_id))


async def _counts(
    session: AsyncSession,
    filters: Sequence[object],
) -> list[IndustryCount]:
    statement = (
        select(UserPolygon.category, func.count(UserPolygon.id))
        .where(*filters)
        .group_by(UserPolygon.category)
        .order_by(UserPolygon.category)
    )
    rows = (await session.execute(statement)).all()
    return [IndustryCount(category=category, count=int(count)) for category, count in rows]


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
            select(PolygonAnalysisArea.polygon_id).where(PolygonAnalysisArea.analysis_area_id == area.id)
        ))
    category_counts = await _counts(session, base_filters)

    selected_filters = polygon_filter_clauses(filter_params)
    if area:
        selected_filters.append(UserPolygon.id.in_(
            select(PolygonAnalysisArea.polygon_id).where(PolygonAnalysisArea.analysis_area_id == area.id)
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


async def _benchmark_metrics(
    session: AsyncSession, filters: Sequence[object]
) -> BenchmarkMetrics:
    area = func.ST_Area(func.ST_Transform(UserPolygon.geometry, 25832))
    area_size = UserPolygon.properties["size"].as_string()
    floor_group = floor_group_expression()
    statement = select(
        func.count(UserPolygon.id).label("polygon_count"),
        func.sum(area).label("total_area_m2"),
        func.avg(area).label("average_area_m2"),
        func.percentile_cont(0.5).within_group(area).label("median_area_m2"),
        func.sum(area).filter(UserPolygon.occupancy_status == "VACANT").label("vacant_area_m2"),
        func.sum(area).filter(UserPolygon.occupancy_status != "UNKNOWN").label("known_occupancy_area_m2"),
        func.count(UserPolygon.id).filter(UserPolygon.occupancy_status != "UNKNOWN").label("known_occupancy_count"),
        func.count(UserPolygon.id).filter(UserPolygon.occupancy_status == "VACANT").label("vacant_count"),
        func.count(UserPolygon.id).filter(UserPolygon.business_structure != "UNKNOWN").label("known_business_count"),
        func.count(UserPolygon.id).filter(UserPolygon.business_structure == "CHAIN").label("chain_count"),
        func.max(UserPolygon.updated_at).label("data_updated_at"),
        *[
            func.count(UserPolygon.id).filter(area_size == key).label(f"size_{key.lower()}_count")
            for key in ("S", "M", "L", "XL")
        ],
        *[
            func.count(UserPolygon.id).filter(floor_group == key).label(f"floor_{key.lower()}_count")
            for key in ("UG", "EG", "OG")
        ],
        func.count(UserPolygon.id).filter(UserPolygon.occupancy_status == "OCCUPIED").label("occupied_count"),
        func.count(UserPolygon.id).filter(UserPolygon.business_structure == "INDEPENDENT").label("independent_count"),
        func.count(UserPolygon.id).filter(UserPolygon.category != "custom").label("known_category_count"),
        func.count(UserPolygon.id).filter(floor_group.is_not(None)).label("known_floor_count"),
        func.count(UserPolygon.id).filter(area_size.is_not(None)).label("known_size_count"),
    ).where(*filters)
    row = (await session.execute(statement)).mappings().one()
    known_occupancy = int(row["known_occupancy_count"] or 0)
    known_business = int(row["known_business_count"] or 0)
    vacant = int(row["vacant_count"] or 0)
    chains = int(row["chain_count"] or 0)
    polygon_count = int(row["polygon_count"] or 0)
    vacant_area = float(row["vacant_area_m2"]) if row.get("vacant_area_m2") is not None else None
    known_occupancy_area = float(row["known_occupancy_area_m2"]) if row.get("known_occupancy_area_m2") is not None else None

    def distribution(prefix: str, values: Sequence[tuple[str, str]]) -> list[DimensionCount]:
        return [DimensionCount(key=key, label=label, count=int(row.get(f"{prefix}_{key.lower()}_count") or 0)) for key, label in values]

    def completeness(key: str, label: str, complete: int) -> CompletenessMetric:
        return CompletenessMetric(
            key=key, label=label, complete=complete, total=polygon_count,
            percent=round(complete / polygon_count * 100, 1) if polygon_count else None,
        )

    return BenchmarkMetrics(
        polygon_count=polygon_count,
        occupied_count=known_occupancy - vacant,
        vacant_count=vacant,
        chain_count=chains,
        independent_count=known_business - chains,
        total_area_m2=float(row["total_area_m2"]) if row["total_area_m2"] is not None else None,
        average_area_m2=float(row["average_area_m2"]) if row["average_area_m2"] is not None else None,
        median_area_m2=(float(row["median_area_m2"]) if row.get("median_area_m2") is not None else None),
        vacant_area_m2=vacant_area,
        vacancy_area_rate=(round(vacant_area / known_occupancy_area * 100, 2) if vacant_area is not None and known_occupancy_area else None),
        vacancy_rate=(round(vacant / known_occupancy * 100, 2) if known_occupancy else None),
        chain_store_rate=(round(chains / known_business * 100, 2) if known_business else None),
        known_occupancy_count=known_occupancy,
        known_business_structure_count=known_business,
        data_updated_at=row.get("data_updated_at"),
        size_distribution=[
            *distribution("size", (("S", "S"), ("M", "M"), ("L", "L"), ("XL", "XL"))),
            DimensionCount(key="UNKNOWN", label="Ohne Angabe", count=polygon_count - int(row.get("known_size_count") or 0)),
        ],
        floor_distribution=[
            *distribution("floor", (("UG", "UG"), ("EG", "EG"), ("OG", "OG"))),
            DimensionCount(key="UNKNOWN", label="Ohne Angabe", count=polygon_count - int(row.get("known_floor_count") or 0)),
        ],
        status_distribution=[
            DimensionCount(key="OCCUPIED", label="Belegt", count=int(row.get("occupied_count") or (known_occupancy - vacant))),
            DimensionCount(key="VACANT", label="Leerstehend", count=vacant),
            DimensionCount(key="UNKNOWN", label="Ohne Angabe", count=polygon_count - known_occupancy),
        ],
        business_structure_distribution=[
            DimensionCount(key="CHAIN", label="Filiale", count=chains),
            DimensionCount(key="INDEPENDENT", label="Inhabergeführt", count=int(row.get("independent_count") or (known_business - chains))),
            DimensionCount(key="UNKNOWN", label="Ohne Angabe", count=polygon_count - known_business),
        ],
        data_completeness=[
            completeness("category", "Branche", int(row.get("known_category_count") or 0)),
            completeness("area_size", "Größenklasse", int(row.get("known_size_count") or 0)),
            completeness("floor", "Etage", int(row.get("known_floor_count") or 0)),
            completeness("occupancy_status", "Belegungsstatus", known_occupancy),
            completeness("business_structure", "Betriebsform", known_business),
        ],
    )


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
        municipality = area if area.area_type == "MUNICIPALITY" else await session.scalar(
            select(AnalysisArea).where(AnalysisArea.area_type == "MUNICIPALITY", func.ST_Covers(AnalysisArea.geometry, area.centroid)).limit(1)
        )
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

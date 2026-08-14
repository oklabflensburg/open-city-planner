import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_area import AnalysisArea, PolygonAnalysisArea
from app.models.user_polygon import UserPolygon
from app.schemas.analytics import (
    AnalyticsFastFacts,
    AnalyticsOverview,
    BenchmarkMetrics,
    IndustryCount,
    MarketBenchmark,
    MarketBenchmarkResult,
    PrimeRentData,
)
from app.services.city_metrics import get_public_city_metrics

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
    analysis_area_id: int | None = None,
) -> list[object]:
    filters: list[object] = []
    if floors:
        filters.append(func.coalesce(UserPolygon.floor, "EG").in_(floors))
    if area_sizes:
        filters.append(
            func.coalesce(UserPolygon.properties["size"].as_string(), "M").in_(area_sizes)
        )
    if occupancy_statuses:
        filters.append(UserPolygon.occupancy_status.in_(occupancy_statuses))
    if business_structures:
        filters.append(UserPolygon.business_structure.in_(business_structures))
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


async def analytics_overview(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    area_id: uuid.UUID | None = None,
) -> AnalyticsOverview:
    area = await _resolve_area(session, area_id)
    base_filters = _base_filters(floors, area_sizes, occupancy_statuses, business_structures, area.id if area else None)
    category_counts = await _counts(session, base_filters)

    selected_filters = list(base_filters)
    if categories:
        selected_filters.append(UserPolygon.category.in_(categories))
    distribution = await _counts(session, selected_filters)

    shops = sum(
        item.count for item in distribution if item.category in SHOP_CATEGORIES
    )
    calculated = await _benchmark_metrics(session, selected_filters)
    city_metrics = await get_public_city_metrics(session)

    return AnalyticsOverview(
        fast_facts=AnalyticsFastFacts(
            shops=shops,
            total_area_m2=calculated.total_area_m2,
            average_area_m2=calculated.average_area_m2,
            calculated_vacancy_rate=calculated.vacancy_rate,
            calculated_chain_store_rate=calculated.chain_store_rate,
            known_occupancy_count=calculated.known_occupancy_count,
            known_business_structure_count=calculated.known_business_structure_count,
            **city_metrics.model_dump(),
        ),
        industry_distribution=distribution,
        category_counts=category_counts,
        # price_per_sqm is an internal management field, not a public rent dataset.
        prime_rents=PrimeRentData(),
    )


async def _benchmark_metrics(
    session: AsyncSession, filters: Sequence[object]
) -> BenchmarkMetrics:
    area = func.ST_Area(func.ST_Transform(UserPolygon.geometry, 25832))
    statement = select(
        func.count(UserPolygon.id).label("polygon_count"),
        func.sum(area).label("total_area_m2"),
        func.avg(area).label("average_area_m2"),
        func.percentile_cont(0.5).within_group(area).label("median_area_m2"),
        func.count(UserPolygon.id).filter(UserPolygon.occupancy_status != "UNKNOWN").label("known_occupancy_count"),
        func.count(UserPolygon.id).filter(UserPolygon.occupancy_status == "VACANT").label("vacant_count"),
        func.count(UserPolygon.id).filter(UserPolygon.business_structure != "UNKNOWN").label("known_business_count"),
        func.count(UserPolygon.id).filter(UserPolygon.business_structure == "CHAIN").label("chain_count"),
        func.max(UserPolygon.updated_at).label("data_updated_at"),
    ).where(*filters)
    row = (await session.execute(statement)).mappings().one()
    known_occupancy = int(row["known_occupancy_count"] or 0)
    known_business = int(row["known_business_count"] or 0)
    vacant = int(row["vacant_count"] or 0)
    chains = int(row["chain_count"] or 0)
    return BenchmarkMetrics(
        polygon_count=int(row["polygon_count"] or 0),
        occupied_count=known_occupancy - vacant,
        vacant_count=vacant,
        chain_count=chains,
        independent_count=known_business - chains,
        total_area_m2=float(row["total_area_m2"]) if row["total_area_m2"] is not None else None,
        average_area_m2=float(row["average_area_m2"]) if row["average_area_m2"] is not None else None,
        median_area_m2=(float(row["median_area_m2"]) if row.get("median_area_m2") is not None else None),
        vacancy_rate=(round(vacant / known_occupancy * 100, 2) if known_occupancy else None),
        chain_store_rate=(round(chains / known_business * 100, 2) if known_business else None),
        known_occupancy_count=known_occupancy,
        known_business_structure_count=known_business,
        data_updated_at=row.get("data_updated_at"),
    )


async def market_benchmarks(
    session: AsyncSession,
    *,
    categories: Sequence[str] = (),
    floors: Sequence[str] = (),
    area_sizes: Sequence[str] = (),
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    area_id: uuid.UUID | None = None,
) -> MarketBenchmarkResult:
    area = await _resolve_area(session, area_id)
    selected_filters = _base_filters(floors, area_sizes, occupancy_statuses, business_structures, area.id if area else None)
    if categories:
        selected_filters.append(UserPolygon.category.in_(categories))
    selected = await _benchmark_metrics(session, selected_filters)
    municipality = None
    if area is not None:
        municipality = area if area.area_type == "MUNICIPALITY" else await session.scalar(
            select(AnalysisArea).where(AnalysisArea.area_type == "MUNICIPALITY", func.ST_Covers(AnalysisArea.geometry, area.centroid)).limit(1)
        )
    city_filters = _base_filters(floors, area_sizes, occupancy_statuses, business_structures, municipality.id if municipality else None)
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

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_verwaltung_user
from app.cache.service import last_cache_status
from app.core.config import get_settings
from app.db.session import get_session
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsOverview,
    AreaCompareRequest,
    AreaCompareResult,
    CityMetricsPublicRead,
    CityMetricsUpdate,
    CityMetricsVerwaltungRead,
    MarketBenchmarkResult,
)
from app.schemas.polygon_filters import PolygonFilterParams, polygon_filter_query
from app.services.analytics import analytics_overview, compare_areas, market_benchmarks
from app.services.city_metrics import (
    get_public_city_metrics,
    get_verwaltung_city_metrics,
    update_city_metrics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/fast-facts", response_model=CityMetricsPublicRead)
async def get_fast_facts(session: SessionDep) -> CityMetricsPublicRead:
    return await get_public_city_metrics(session)


@router.get("/fast-facts/verwaltung", response_model=CityMetricsVerwaltungRead)
async def get_fast_facts_verwaltung(
    response: Response,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_verwaltung_user)],
) -> CityMetricsVerwaltungRead:
    response.headers["Cache-Control"] = "private, no-store"
    return await get_verwaltung_city_metrics(session)


@router.patch("/fast-facts", response_model=CityMetricsVerwaltungRead)
async def patch_fast_facts(
    payload: CityMetricsUpdate,
    response: Response,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_verwaltung_user)],
) -> CityMetricsVerwaltungRead:
    response.headers["Cache-Control"] = "private, no-store"
    return await update_city_metrics(session, payload, current_user.id)


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    session: SessionDep,
    response: Response,
    filters: Annotated[PolygonFilterParams, Depends(polygon_filter_query)],
    area_id: uuid.UUID | None = None,
) -> AnalyticsOverview:
    result = await analytics_overview(
        session,
        categories=filters.categories,
        floors=filters.floors,
        area_sizes=filters.area_sizes,
        occupancy_statuses=filters.occupancy_statuses,
        business_structures=filters.business_structures,
        sources=filters.sources,
        area_id=area_id,
    )
    if get_settings().cache_debug_headers and (status := last_cache_status()):
        response.headers["X-Cache"] = status
    return result


@router.get("/benchmarks", response_model=MarketBenchmarkResult)
async def get_market_benchmarks(
    session: SessionDep,
    response: Response,
    filters: Annotated[PolygonFilterParams, Depends(polygon_filter_query)],
    area_id: uuid.UUID | None = None,
) -> MarketBenchmarkResult:
    result = await market_benchmarks(
        session,
        categories=filters.categories,
        floors=filters.floors,
        area_sizes=filters.area_sizes,
        occupancy_statuses=filters.occupancy_statuses,
        business_structures=filters.business_structures,
        sources=filters.sources,
        area_id=area_id,
    )
    if get_settings().cache_debug_headers and (status := last_cache_status()):
        response.headers["X-Cache"] = status
    return result


@router.post(
    "/compare",
    response_model=AreaCompareResult,
    summary="Gemeinden, Stadtteile und Quartiere gemeinsam vergleichen",
    description=(
        "Berechnet alle gewählten Gebiete und optional die zugehörige Gemeinde als Benchmark "
        "in einem Request mit derselben Filtergrundlage."
    ),
)
async def post_area_comparison(
    payload: AreaCompareRequest,
    session: SessionDep,
    response: Response,
) -> AreaCompareResult:
    result = await compare_areas(session, payload)
    if get_settings().cache_debug_headers and (status := last_cache_status()):
        response.headers["X-Cache"] = status
    return result

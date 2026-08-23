import uuid
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import last_cache_status
from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.analysis_area import (
    AnalysisAreaAnalytics,
    AnalysisAreaComparison,
    AnalysisAreaDetail,
    AnalysisAreaPolygon,
    AnalysisAreaRead,
    AnalysisAreaSitemapEntry,
)
from app.schemas.polygon_filters import PolygonFilterParams, polygon_filter_query
from app.schemas.statistics import AreaStatisticSeriesRead, AreaStatisticsRead
from app.services.analysis_area_api import (
    analysis_area_sitemap_entries,
    area_analytics,
    area_comparison,
    area_detail,
    area_detail_by_slug,
    area_polygons_by_slug,
    area_uuid_by_slug,
    areas_geojson,
    list_areas,
)
from app.services.area_statistics import area_statistic_series, area_statistics
from app.services.public_query_security import guard_public_query, is_statement_timeout_error

router = APIRouter(prefix="/analysis-areas", tags=["Analysis Areas"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ANALYTICS_TIMEOUT_DETAIL = {
    "error": {
        "code": "ANALYTICS_QUERY_TIMEOUT",
        "message": "Die Gebietsanalyse konnte nicht rechtzeitig abgeschlossen werden.",
    }
}


async def _raise_analytics_database_error(session: AsyncSession, error: DBAPIError) -> NoReturn:
    if not is_statement_timeout_error(error):
        raise error
    await session.rollback()
    raise HTTPException(
        status_code=503,
        detail=ANALYTICS_TIMEOUT_DETAIL,
    ) from error


@router.get("", response_model=list[AnalysisAreaRead], summary="Analysegebiete auflisten")
async def get_areas(
    session: SessionDep,
    area_type: Annotated[str | None, Query()] = None,
    parent_id: uuid.UUID | None = None,
) -> list[AnalysisAreaRead]:
    if area_type and area_type not in {"MUNICIPALITY", "DISTRICT", "QUARTER"}:
        raise HTTPException(422, "Ungültiger Gebietstyp.")
    return await list_areas(session, area_type, parent_id)


@router.get("/geojson", summary="Analysegebiete als GeoJSON laden")
async def get_areas_geojson(
    session: SessionDep,
    response: Response,
    limit: Annotated[int, Query(ge=1)] = get_settings().public_polygon_response_limit,
) -> dict:
    response.headers["Cache-Control"] = "public, max-age=300"
    result = await areas_geojson(session, limit=limit)
    if get_settings().cache_debug_headers and (status := last_cache_status()):
        response.headers["X-Cache"] = status
    return result


@router.get(
    "/sitemap",
    response_model=list[AnalysisAreaSitemapEntry],
    summary="Indexierbare Gebietsseiten auflisten",
)
async def get_area_sitemap(session: SessionDep) -> list[AnalysisAreaSitemapEntry]:
    return await analysis_area_sitemap_entries(session)


@router.get(
    "/by-slug/{slug}",
    response_model=AnalysisAreaDetail,
    summary="Öffentliches Gebiet per Slug laden",
)
async def get_area_by_slug(slug: str, session: SessionDep) -> AnalysisAreaDetail:
    result = await area_detail_by_slug(session, slug)
    if result is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    return result


@router.get(
    "/by-slug/{slug}/polygons",
    response_model=list[AnalysisAreaPolygon],
    summary="Verkaufsflächen eines Gebiets laden",
)
async def get_area_polygons_by_slug(
    slug: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> list[AnalysisAreaPolygon]:
    result = await area_polygons_by_slug(session, slug, limit)
    if result is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    return result


@router.get(
    "/by-slug/{slug}/statistics",
    response_model=AreaStatisticsRead,
    summary="Kommunale Statistik eines Gebiets laden",
    description="Liefert lokal importierte Zahlenspiegel-Daten mit Quelle, Periode und Gebietsebene.",
    tags=["Statistics"],
)
async def get_area_statistics(
    slug: str, session: SessionDep, request: Request
) -> AreaStatisticsRead:
    await guard_public_query(request, session, "area-statistics")
    result = await area_statistics(session, slug)
    if result is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    return result


@router.get(
    "/by-slug/{slug}/statistics/{metric_key}",
    response_model=AreaStatisticSeriesRead,
    summary="Zeitreihe einer kommunalen Gebietskennzahl laden",
    tags=["Statistics"],
)
async def get_area_statistic_series(
    slug: str, metric_key: str, session: SessionDep, request: Request
) -> AreaStatisticSeriesRead:
    await guard_public_query(request, session, "area-statistic-series")
    result = await area_statistic_series(session, slug, metric_key)
    if result is None:
        raise HTTPException(404, "Die Gebietsstatistik wurde nicht gefunden.")
    return result


@router.get("/{area_id}", response_model=AnalysisAreaRead, summary="Analysegebiet per ID laden")
async def get_area(area_id: uuid.UUID, session: SessionDep) -> AnalysisAreaRead:
    result = await area_detail(session, area_id)
    if result is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    return result


def filters(params: PolygonFilterParams) -> dict:
    return {
        "categories": params.categories,
        "floors": params.floors,
        "area_sizes": params.area_sizes,
        "occupancy_statuses": params.occupancy_statuses,
        "business_structures": params.business_structures,
        "sources": params.sources,
    }


@router.get(
    "/by-slug/{slug}/analytics",
    response_model=AnalysisAreaAnalytics,
    summary="Aggregierte Gebietskennzahlen per Slug laden",
)
async def get_area_analytics_by_slug(
    slug: str, session: SessionDep, request: Request
) -> AnalysisAreaAnalytics:
    await guard_public_query(request, session, "area-analytics")
    try:
        area_id = await area_uuid_by_slug(session, slug)
        if area_id is None:
            raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
        result = await area_analytics(session, area_id, **filters(PolygonFilterParams()))
    except DBAPIError as exc:
        await _raise_analytics_database_error(session, exc)
    if result is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    return result


@router.get(
    "/by-slug/{slug}/comparison",
    response_model=AnalysisAreaComparison,
    summary="Gebiet mit der Gesamtstadt vergleichen",
)
async def get_area_comparison_by_slug(
    slug: str, session: SessionDep, request: Request
) -> AnalysisAreaComparison:
    await guard_public_query(request, session, "area-comparison")
    area_id = await area_uuid_by_slug(session, slug)
    if area_id is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    result = await area_comparison(session, area_id, **filters(PolygonFilterParams()))
    if result is None:
        raise HTTPException(404, "Das Gebiet oder die zugehörige Gemeinde wurde nicht gefunden.")
    return result


@router.get(
    "/{area_id}/analytics",
    response_model=AnalysisAreaAnalytics,
    summary="Gefilterte Gebietskennzahlen laden",
)
async def get_area_analytics(
    area_id: uuid.UUID,
    session: SessionDep,
    request: Request,
    filter_params: Annotated[PolygonFilterParams, Depends(polygon_filter_query)],
) -> AnalysisAreaAnalytics:
    await guard_public_query(request, session, "area-analytics")
    try:
        result = await area_analytics(session, area_id, **filters(filter_params))
    except DBAPIError as exc:
        await _raise_analytics_database_error(session, exc)
    if result is None:
        raise HTTPException(404, "Das Gebiet wurde nicht gefunden.")
    return result


@router.get(
    "/{area_id}/comparison",
    response_model=AnalysisAreaComparison,
    summary="Gefilterten Gesamtstadtvergleich laden",
)
async def get_area_comparison(
    area_id: uuid.UUID,
    session: SessionDep,
    request: Request,
    filter_params: Annotated[PolygonFilterParams, Depends(polygon_filter_query)],
) -> AnalysisAreaComparison:
    await guard_public_query(request, session, "area-comparison")
    result = await area_comparison(session, area_id, **filters(filter_params))
    if result is None:
        raise HTTPException(404, "Das Gebiet oder die zugehörige Gemeinde wurde nicht gefunden.")
    return result

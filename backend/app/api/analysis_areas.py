import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics import (
    AREA_SIZES,
    BUSINESS_STRUCTURES,
    CATEGORIES,
    FLOORS,
    OCCUPANCY_STATUSES,
    _checked,
)
from app.cache.service import last_cache_status
from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.analysis_area import (
    AnalysisAreaAnalytics,
    AnalysisAreaComparison,
    AnalysisAreaRead,
)
from app.services.analysis_area_api import (
    area_analytics,
    area_comparison,
    area_detail,
    areas_geojson,
    list_areas,
)

router = APIRouter(prefix="/analysis-areas", tags=["analysis-areas"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[AnalysisAreaRead])
async def get_areas(session: SessionDep, area_type: Annotated[str | None, Query()] = None, parent_id: uuid.UUID | None = None) -> list[AnalysisAreaRead]:
    if area_type and area_type not in {"MUNICIPALITY", "DISTRICT", "QUARTER"}:
        raise HTTPException(422, "Invalid area_type")
    return await list_areas(session, area_type, parent_id)


@router.get("/geojson")
async def get_areas_geojson(session: SessionDep, response: Response) -> dict:
    response.headers["Cache-Control"] = "public, max-age=300"
    result = await areas_geojson(session)
    if get_settings().cache_debug_headers and (status := last_cache_status()):
        response.headers["X-Cache"] = status
    return result


@router.get("/{area_id}", response_model=AnalysisAreaRead)
async def get_area(area_id: uuid.UUID, session: SessionDep) -> AnalysisAreaRead:
    result = await area_detail(session, area_id)
    if result is None:
        raise HTTPException(404, "Analysis area not found")
    return result


def filters(categories: str | None, floors: str | None, area_sizes: str | None, occupancy_statuses: str | None, business_structures: str | None) -> dict:
    return {
        "categories": _checked(categories, CATEGORIES, "categories"),
        "floors": _checked(floors, FLOORS, "floors"),
        "area_sizes": _checked(area_sizes, AREA_SIZES, "area_sizes"),
        "occupancy_statuses": _checked(occupancy_statuses, OCCUPANCY_STATUSES, "occupancy_statuses"),
        "business_structures": _checked(business_structures, BUSINESS_STRUCTURES, "business_structures"),
    }


@router.get("/{area_id}/analytics", response_model=AnalysisAreaAnalytics)
async def get_area_analytics(
    area_id: uuid.UUID, session: SessionDep, categories: str | None = None, floors: str | None = None,
    area_sizes: str | None = None, occupancy_statuses: str | None = None, business_structures: str | None = None,
) -> AnalysisAreaAnalytics:
    result = await area_analytics(session, area_id, **filters(categories, floors, area_sizes, occupancy_statuses, business_structures))
    if result is None:
        raise HTTPException(404, "Analysis area not found")
    return result


@router.get("/{area_id}/comparison", response_model=AnalysisAreaComparison)
async def get_area_comparison(
    area_id: uuid.UUID, session: SessionDep, categories: str | None = None, floors: str | None = None,
    area_sizes: str | None = None, occupancy_statuses: str | None = None, business_structures: str | None = None,
) -> AnalysisAreaComparison:
    result = await area_comparison(session, area_id, **filters(categories, floors, area_sizes, occupancy_statuses, business_structures))
    if result is None:
        raise HTTPException(404, "Analysis area or municipality not found")
    return result

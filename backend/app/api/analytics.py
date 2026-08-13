from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_verwaltung_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsOverview,
    CityMetricsPublicRead,
    CityMetricsUpdate,
    CityMetricsVerwaltungRead,
)
from app.services.analytics import analytics_overview
from app.services.city_metrics import (
    get_public_city_metrics,
    get_verwaltung_city_metrics,
    update_city_metrics,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _split(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


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
    categories: Annotated[str | None, Query()] = None,
    floors: Annotated[str | None, Query()] = None,
    area_sizes: Annotated[str | None, Query()] = None,
) -> AnalyticsOverview:
    return await analytics_overview(
        session,
        categories=_split(categories),
        floors=_split(floors),
        area_sizes=_split(area_sizes),
    )

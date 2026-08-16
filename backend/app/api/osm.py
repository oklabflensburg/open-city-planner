import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import last_cache_status
from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.osm import OsmObjectInfo, OsmViewportFeatureCollection, OsmViewportQuery
from app.services.osm_features import (
    osm_feature_detail,
    selected_categories,
    viewport_features_json,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/osm", tags=["OpenStreetMap"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/features", response_model=OsmViewportFeatureCollection)
async def get_osm_viewport_features(
    request: Request,
    session: SessionDep,
    query: Annotated[OsmViewportQuery, Query()],
):
    settings = get_settings()
    check_rate_limit(
        f"osm-viewport:{request.client.host if request.client else 'unknown'}",
        attempts=settings.osm_viewport_rate_limit_attempts,
        window_seconds=settings.osm_viewport_rate_limit_window_seconds,
        code="OSM_VIEWPORT_RATE_LIMITED",
        message="Zu viele Kartenabfragen. Bitte kurz warten.",
    )
    try:
        selected_categories(query.categories)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = await viewport_features_json(session, query)
    etag = f'"{hashlib.sha256(payload).hexdigest()[:20]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "public, max-age=20"})
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=20, stale-while-revalidate=40",
    }
    if settings.cache_debug_headers and (cache_status := last_cache_status()):
        headers["X-Cache"] = cache_status
    return Response(content=payload, media_type="application/json", headers=headers)


@router.get("/features/{osm_type}/{osm_id}", response_model=OsmObjectInfo)
async def get_osm_feature_detail(
    osm_type: Literal["node", "way", "relation"], osm_id: int, session: SessionDep
) -> OsmObjectInfo:
    result = await osm_feature_detail(session, osm_type=osm_type, osm_id=osm_id)
    if result is None:
        raise HTTPException(status_code=404, detail="OSM feature not found")
    return result

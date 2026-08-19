import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.auth.dependencies import (
    can_create_polygon,
    can_delete_polygon,
    can_edit_polygon,
    get_current_active_user,
    get_verified_user,
    require_verwaltung_user,
)
from app.db.session import get_session
from app.models.user import User
from app.schemas.analytics import ComparableResult, LocationAnalysis
from app.schemas.geojson import (
    FeatureCollection,
    PolygonCreate,
    PolygonEditorRead,
    PolygonMetrics,
    PolygonOverviewRead,
    PolygonRead,
    PolygonSitemapEntry,
    PolygonUpdate,
    PolygonVerwaltungRead,
    PolygonVerwaltungUpdate,
    PublicPolygonDetail,
)
from app.schemas.osm import OsmPolygonImportRead, OsmPolygonImportRequest, PolygonOsmInfo
from app.schemas.polygon_filters import PolygonFilterParams, polygon_filter_query
from app.services.comparables import comparable_polygons
from app.services.geometry import GeometryValidationError
from app.services.location_analytics import polygon_location_analysis
from app.services.osm_import import (
    OsmImportAlreadyExists,
    OsmImportGeometryRequired,
    OsmImportNotFound,
    OsmImportNotImportable,
    create_polygon_from_osm,
)
from app.services.osm_lookup import OsmLookupError, OsmLookupService
from app.services.polygons import (
    create_polygon,
    delete_polygon,
    get_polygon,
    list_polygon_overview,
    list_polygons,
    polygon_editor_detail,
    polygon_metrics,
    polygon_sitemap_entries,
    polygon_verwaltung_detail,
    polygons_geojson,
    public_polygon_by_slug,
    read_polygon,
    update_polygon,
    update_polygon_verwaltung,
)
from app.services.public_query_security import guard_public_query

router = APIRouter(prefix="/polygons", tags=["Polygons"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[PolygonRead])
async def get_polygons(session: SessionDep) -> list[PolygonRead]:
    return await list_polygons(session)


@router.post("", response_model=PolygonRead, status_code=status.HTTP_201_CREATED)
async def post_polygon(
    payload: PolygonCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_verified_user)],
) -> PolygonRead:
    if not can_create_polygon(current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Für das Anlegen einer Fläche fehlen die erforderlichen Berechtigungen.",
                }
            },
        )
    try:
        return await create_polygon(session, payload, current_user.id)
    except GeometryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/from-osm", response_model=OsmPolygonImportRead, status_code=status.HTTP_201_CREATED)
async def post_polygon_from_osm(
    payload: OsmPolygonImportRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_verified_user)],
) -> OsmPolygonImportRead:
    if not can_create_polygon(current_user):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Für das Anlegen einer Fläche fehlen die erforderlichen Berechtigungen.",
                }
            },
        )
    try:
        return await create_polygon_from_osm(session, payload, current_user.id)
    except OsmImportNotFound as exc:
        await session.rollback()
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OSM_FEATURE_NOT_FOUND",
                    "message": "Das lokale OSM-Objekt wurde nicht gefunden.",
                }
            },
        ) from exc
    except OsmImportGeometryRequired as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "OSM_GEOMETRY_REQUIRED",
                    "message": "Für diesen OSM-Punkt muss eine Fläche eingezeichnet werden.",
                }
            },
        ) from exc
    except OsmImportNotImportable as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "OSM_FEATURE_NOT_IMPORTABLE",
                    "message": "Dieses OSM-Objekt kann nicht als Stadtplaner-Fläche übernommen werden.",
                }
            },
        ) from exc
    except OsmImportAlreadyExists as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "OSM_FEATURE_ALREADY_IMPORTED",
                    "message": "Das OSM-Objekt wurde für diese Etage bereits übernommen.",
                    "polygon_id": exc.polygon_id,
                    "slug": exc.slug,
                }
            },
        ) from exc
    except GeometryValidationError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/geojson", response_model=FeatureCollection)
async def get_geojson(session: SessionDep) -> FeatureCollection:
    return await polygons_geojson(session)


@router.get("/overview", response_model=list[PolygonOverviewRead])
async def get_polygon_overview(
    session: SessionDep,
    filters: Annotated[PolygonFilterParams, Depends(polygon_filter_query)],
) -> list[PolygonOverviewRead]:
    return await list_polygon_overview(session, filters)


@router.get("/sitemap", response_model=list[PolygonSitemapEntry])
async def get_polygon_sitemap(session: SessionDep) -> list[PolygonSitemapEntry]:
    return await polygon_sitemap_entries(session)


@router.get("/by-slug/{slug}", response_model=PublicPolygonDetail)
async def get_polygon_by_slug(slug: str, session: SessionDep) -> PublicPolygonDetail:
    polygon = await public_polygon_by_slug(session, slug)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return polygon


@router.get(
    "/by-slug/{slug}/osm",
    response_model=PolygonOsmInfo,
    response_model_exclude_none=True,
)
async def get_polygon_osm_by_slug(slug: str, session: SessionDep) -> PolygonOsmInfo:
    try:
        result = await OsmLookupService().find_osm_objects_for_polygon(session, slug=slug)
    except OsmLookupError as exc:
        raise HTTPException(
            status_code=503, detail="Die OpenStreetMap-Abfrage ist fehlgeschlagen."
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return result


@router.get("/by-slug/{slug}/location", response_model=LocationAnalysis)
async def get_polygon_location_analysis(
    slug: str,
    session: SessionDep,
    request: Request,
    radius_m: Annotated[int, Query(ge=100, le=2000)] = 500,
) -> LocationAnalysis:
    await guard_public_query(request, session, "polygon-location")
    result = await polygon_location_analysis(session, slug=slug, radius_m=radius_m)
    if result is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return result


@router.get("/by-slug/{slug}/comparables", response_model=ComparableResult)
async def get_polygon_comparables(
    slug: str,
    session: SessionDep,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> ComparableResult:
    await guard_public_query(request, session, "polygon-comparables")
    result = await comparable_polygons(session, slug=slug, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return result


@router.get(
    "/{polygon_id}/osm",
    response_model=PolygonOsmInfo,
    response_model_exclude_none=True,
)
async def get_polygon_osm_by_id(polygon_id: uuid.UUID, session: SessionDep) -> PolygonOsmInfo:
    try:
        result = await OsmLookupService().find_osm_objects_for_polygon(
            session, polygon_id=str(polygon_id)
        )
    except OsmLookupError as exc:
        raise HTTPException(
            status_code=503, detail="Die OpenStreetMap-Abfrage ist fehlgeschlagen."
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return result


@router.get("/{polygon_id}", response_model=PolygonRead)
async def get_polygon_by_id(polygon_id: uuid.UUID, session: SessionDep) -> PolygonRead:
    polygon = await read_polygon(session, polygon_id)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return polygon


@router.put("/{polygon_id}", response_model=PolygonRead)
async def put_polygon(
    polygon_id: uuid.UUID,
    payload: PolygonCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_verified_user)],
) -> PolygonRead:
    polygon = await get_polygon(session, polygon_id, for_update=True)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    if not can_edit_polygon(current_user, polygon.created_by_user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Es können nur eigene Flächen bearbeitet werden.",
                }
            },
        )
    try:
        return await update_polygon(
            session, polygon, PolygonUpdate(**payload.model_dump()), current_user.id
        )
    except GeometryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StaleDataError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.") from exc


@router.patch("/{polygon_id}", response_model=PolygonRead)
async def patch_polygon(
    polygon_id: uuid.UUID,
    payload: PolygonUpdate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_verified_user)],
) -> PolygonRead:
    if payload.model_extra:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FIELD_NOT_ALLOWED",
                    "message": "Diese Felder dürfen hier nicht bearbeitet werden.",
                }
            },
        )
    polygon = await get_polygon(session, polygon_id, for_update=True)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    if not can_edit_polygon(current_user, polygon.created_by_user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Es können nur eigene Flächen bearbeitet werden.",
                }
            },
        )
    try:
        return await update_polygon(session, polygon, payload, current_user.id)
    except GeometryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        if str(exc) == "POLYGON_VERSION_CONFLICT":
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "POLYGON_VERSION_CONFLICT",
                        "message": "Die Fläche wurde zwischenzeitlich geändert.",
                    }
                },
            ) from exc
        raise
    except StaleDataError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.") from exc


@router.get("/{polygon_id}/editor", response_model=PolygonEditorRead)
async def get_polygon_editor(
    polygon_id: uuid.UUID,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> PolygonEditorRead:
    polygon = await get_polygon(session, polygon_id)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    if not can_edit_polygon(current_user, polygon.created_by_user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {"code": "PERMISSION_DENIED", "message": "Keine Bearbeitungsberechtigung."}
            },
        )
    return await polygon_editor_detail(
        session,
        polygon,
        can_delete=can_delete_polygon(current_user, polygon.created_by_user_id),
    )


@router.get("/{polygon_id}/verwaltung", response_model=PolygonVerwaltungRead)
async def get_polygon_verwaltung(
    polygon_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_verwaltung_user)],
) -> PolygonVerwaltungRead:
    response.headers["Cache-Control"] = "private, no-store"
    polygon = await get_polygon(session, polygon_id)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return await polygon_verwaltung_detail(session, polygon)


@router.patch("/{polygon_id}/verwaltung", response_model=PolygonVerwaltungRead)
async def patch_polygon_verwaltung(
    polygon_id: uuid.UUID,
    payload: PolygonVerwaltungUpdate,
    response: Response,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_verwaltung_user)],
) -> PolygonVerwaltungRead:
    response.headers["Cache-Control"] = "private, no-store"
    polygon = await get_polygon(session, polygon_id, for_update=True)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    try:
        return await update_polygon_verwaltung(session, polygon, payload, current_user.id)
    except RuntimeError as exc:
        if str(exc) == "POLYGON_VERSION_CONFLICT":
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "POLYGON_VERSION_CONFLICT",
                        "message": "Die Fläche wurde zwischenzeitlich geändert.",
                    }
                },
            ) from exc
        raise


@router.delete("/{polygon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_polygon(
    polygon_id: uuid.UUID,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_verified_user)],
) -> None:
    polygon = await get_polygon(session, polygon_id, for_update=True)
    if polygon is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    if not can_delete_polygon(current_user, polygon.created_by_user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Es können nur eigene Flächen gelöscht werden.",
                }
            },
        )
    await delete_polygon(session, polygon, current_user.id)


@router.get("/{polygon_id}/metrics", response_model=PolygonMetrics)
async def get_metrics(
    polygon_id: uuid.UUID, session: SessionDep, request: Request
) -> PolygonMetrics:
    await guard_public_query(request, session, "polygon-metrics")
    metrics = await polygon_metrics(session, polygon_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail="Die Fläche wurde nicht gefunden.")
    return metrics

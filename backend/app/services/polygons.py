import logging
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.polygon_osm_source import PolygonOsmSource
from app.models.user_polygon import UserPolygon, utcnow
from app.schemas.geojson import (
    Feature,
    FeatureCollection,
    PolygonCreate,
    PolygonEditorRead,
    PolygonMetrics,
    PolygonOsmSourceRead,
    PolygonOverviewRead,
    PolygonRead,
    PolygonSitemapEntry,
    PolygonUpdate,
    PolygonVerwaltungRead,
    PolygonVerwaltungUpdate,
    PublicPolygonDetail,
)
from app.services.analysis_areas import refresh_polygon_area_assignments
from app.services.geometry import from_wkb_element, to_wkb_element
from app.services.nominatim import NominatimService

METRIC_SRID = 25832
logger = logging.getLogger(__name__)


def serialize_polygon(polygon: UserPolygon) -> PolygonRead:
    return PolygonRead(
        id=str(polygon.uuid),
        slug=polygon.slug,
        name=polygon.name,
        description=polygon.description,
        floor=polygon.floor,
        category=polygon.category,
        geometry=from_wkb_element(polygon.geometry),
        properties=polygon.properties,
        created_by_user_id=str(polygon.created_by_user_id) if polygon.created_by_user_id else None,
        updated_by_user_id=str(polygon.updated_by_user_id) if polygon.updated_by_user_id else None,
        created_at=polygon.created_at.isoformat(),
        updated_at=polygon.updated_at.isoformat(),
    )


async def list_polygons(session: AsyncSession) -> list[PolygonRead]:
    rows = await session.scalars(select(UserPolygon).order_by(UserPolygon.created_at.desc()))
    return [serialize_polygon(row) for row in rows]


async def list_polygon_overview(session: AsyncSession) -> list[PolygonOverviewRead]:
    rows = await session.scalars(select(UserPolygon).order_by(UserPolygon.created_at.desc()))
    return [
        PolygonOverviewRead(
            id=str(row.uuid),
            slug=row.slug,
            name=row.name,
            category=row.category,
            floor=row.floor,
            area_size=(str(row.properties.get("size")) if row.properties.get("size") else None),
            address_display_name=row.address_display_name,
            occupancy_status=row.occupancy_status or "UNKNOWN",
            business_structure=row.business_structure or "UNKNOWN",
            geometry=from_wkb_element(row.geometry),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def get_polygon(
    session: AsyncSession, polygon_id: uuid.UUID, *, for_update: bool = False
) -> UserPolygon | None:
    statement = select(UserPolygon).where(UserPolygon.uuid == polygon_id)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def read_polygon(session: AsyncSession, polygon_id: uuid.UUID) -> PolygonRead | None:
    polygon = await get_polygon(session, polygon_id)
    if polygon is None:
        return None
    return serialize_polygon(polygon)


def slugify_polygon_name(name: str) -> str:
    value = name.strip().lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value)).strip("-")
    return slug[:240].rstrip("-") or "flaeche"


async def generate_unique_polygon_slug(session: AsyncSession, name: str) -> str:
    base = slugify_polygon_name(name)
    existing = set(
        await session.scalars(
            select(UserPolygon.slug).where(
                (UserPolygon.slug == base) | (UserPolygon.slug.like(f"{base}-%"))
            )
        )
    )
    if base not in existing:
        return base
    suffix = 2
    while f"{base}-{suffix}" in existing:
        suffix += 1
    return f"{base}-{suffix}"


def polygon_slug_source(polygon: UserPolygon) -> str:
    parts = [
        polygon.floor,
        polygon.address_street,
        polygon.address_house_number,
        polygon.address_city,
    ]
    useful = [part.strip() for part in parts if part and part.strip()]
    return " ".join(useful) if useful else f"{polygon.floor or 'flaeche'} flaeche {str(polygon.uuid)[:8]}"


def _same_version(actual: datetime, expected: datetime | None) -> bool:
    if expected is None:
        return True
    actual_utc = actual if actual.tzinfo else actual.replace(tzinfo=UTC)
    expected_utc = expected if expected.tzinfo else expected.replace(tzinfo=UTC)
    return abs((actual_utc.astimezone(UTC) - expected_utc.astimezone(UTC)).total_seconds()) < 0.001


async def polygon_point_on_surface(session: AsyncSession, polygon_id: uuid.UUID) -> tuple[float, float] | None:
    row = (
        await session.execute(
            select(
                func.ST_X(func.ST_PointOnSurface(UserPolygon.geometry)).label("longitude"),
                func.ST_Y(func.ST_PointOnSurface(UserPolygon.geometry)).label("latitude"),
            ).where(UserPolygon.uuid == polygon_id)
        )
    ).mappings().first()
    if row is None:
        return None
    return float(row["latitude"]), float(row["longitude"])


async def enrich_polygon_address(session: AsyncSession, polygon: UserPolygon) -> bool:
    """Best-effort enrichment. Geometry has already been committed when this runs."""
    polygon_id = polygon.uuid
    try:
        point = await polygon_point_on_surface(session, polygon.uuid)
        address = await NominatimService().reverse(*point) if point else None
        if address is None:
            polygon.address_lookup_status = "failed"
        else:
            polygon.address_display_name = address.display_name
            polygon.address_street = address.street
            polygon.address_house_number = address.house_number
            polygon.address_postal_code = address.postal_code
            polygon.address_city = address.city
            polygon.address_country = address.country
            polygon.address_lookup_status = "resolved"
        await session.commit()
        await session.refresh(polygon)
        return address is not None
    except Exception:  # noqa: BLE001 - enrichment must never roll back a saved geometry
        await session.rollback()
        try:
            fresh = await get_polygon(session, polygon_id)
            if fresh is not None:
                fresh.address_lookup_status = "failed"
                await session.commit()
                await session.refresh(fresh)
        except Exception:  # noqa: BLE001 - status persistence is best effort as well
            await session.rollback()
        logger.warning("Polygon address lookup failed for polygon_id=%s", polygon_id)
        return False


async def create_polygon(session: AsyncSession, payload: PolygonCreate, user_id: uuid.UUID | None = None) -> PolygonRead:
    polygon_uuid = uuid.uuid4()
    polygon = UserPolygon(
        uuid=polygon_uuid,
        name=payload.name,
        slug=await generate_unique_polygon_slug(
            session, f"{payload.floor or 'flaeche'} flaeche {str(polygon_uuid)[:8]}"
        ),
        description=payload.description,
        floor=payload.floor,
        category=payload.category,
        geometry=to_wkb_element(payload.geometry),
        properties=payload.properties,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    session.add(polygon)
    await session.commit()
    await session.refresh(polygon)
    if await enrich_polygon_address(session, polygon):
        polygon.slug = await generate_unique_polygon_slug(session, polygon_slug_source(polygon))
        await session.commit()
        await session.refresh(polygon)
    await refresh_polygon_area_assignments(session, polygon.id)
    await session.commit()
    return serialize_polygon(polygon)


async def polygon_osm_sources(
    session: AsyncSession, polygon_id: int
) -> list[PolygonOsmSourceRead]:
    rows = await session.scalars(
        select(PolygonOsmSource)
        .where(PolygonOsmSource.polygon_id == polygon_id)
        .order_by(PolygonOsmSource.is_primary.desc(), PolygonOsmSource.imported_at)
    )
    return [
        PolygonOsmSourceRead(
            osm_type=row.osm_type,
            osm_id=row.osm_id,
            is_primary=row.is_primary,
            imported_at=row.imported_at,
        )
        for row in rows
    ]


async def _public_detail(
    session: AsyncSession, polygon: UserPolygon, metrics: PolygonMetrics
) -> PublicPolygonDetail:
    return PublicPolygonDetail(
        id=str(polygon.uuid),
        slug=polygon.slug,
        name=polygon.name,
        description=polygon.description,
        floor=polygon.floor,
        area_size=(
            str(polygon.properties.get("size"))
            if polygon.properties.get("size") in {"S", "M", "L", "XL"}
            else None
        ),
        address_display_name=polygon.address_display_name,
        address_street=polygon.address_street,
        address_house_number=polygon.address_house_number,
        address_postal_code=polygon.address_postal_code,
        address_city=polygon.address_city,
        address_country=polygon.address_country,
        address_lookup_status=polygon.address_lookup_status,
        category=polygon.category,
        occupancy_status=polygon.occupancy_status or "UNKNOWN",
        occupancy_source=polygon.occupancy_source or "UNKNOWN",
        business_structure=polygon.business_structure or "UNKNOWN",
        geometry=from_wkb_element(polygon.geometry),
        area_m2=metrics.area_m2,
        perimeter_m=metrics.perimeter_m,
        centroid=metrics.centroid,
        bbox=metrics.bbox,
        created_at=polygon.created_at,
        updated_at=polygon.updated_at,
        osm_sources=await polygon_osm_sources(session, polygon.id),
    )


async def public_polygon_by_slug(
    session: AsyncSession, slug: str
) -> PublicPolygonDetail | None:
    polygon = await session.scalar(select(UserPolygon).where(UserPolygon.slug == slug))
    if polygon is None:
        return None
    metrics = await polygon_metrics(session, polygon.uuid)
    if metrics is None:
        return None
    return await _public_detail(session, polygon, metrics)


async def polygon_editor_detail(
    session: AsyncSession,
    polygon: UserPolygon,
    *,
    can_delete: bool = False,
) -> PolygonEditorRead:
    metrics = await polygon_metrics(session, polygon.uuid)
    if metrics is None:
        raise LookupError("Polygon not found")
    return PolygonEditorRead(
        **(await _public_detail(session, polygon, metrics)).model_dump(),
        can_delete=can_delete,
    )


async def polygon_verwaltung_detail(session: AsyncSession, polygon: UserPolygon) -> PolygonVerwaltungRead:
    metrics = await polygon_metrics(session, polygon.uuid)
    if metrics is None:
        raise LookupError("Polygon not found")
    return PolygonVerwaltungRead(
        **(await _public_detail(session, polygon, metrics)).model_dump(),
        owner_name=polygon.owner_name,
        owner_street=polygon.owner_street,
        owner_house_number=polygon.owner_house_number,
        owner_postal_code=polygon.owner_postal_code,
        owner_city=polygon.owner_city,
        owner_country=polygon.owner_country,
        price_per_sqm=polygon.price_per_sqm,
        occupancy_source_tag=polygon.occupancy_source_tag,
        occupancy_source_updated_at=polygon.occupancy_source_updated_at,
        created_by_user_id=str(polygon.created_by_user_id) if polygon.created_by_user_id else None,
        updated_by_user_id=str(polygon.updated_by_user_id) if polygon.updated_by_user_id else None,
    )


async def polygon_sitemap_entries(session: AsyncSession) -> list[PolygonSitemapEntry]:
    rows = await session.execute(
        select(UserPolygon.slug, UserPolygon.updated_at).order_by(UserPolygon.slug.asc())
    )
    return [PolygonSitemapEntry(slug=row.slug, updated_at=row.updated_at) for row in rows]


async def update_polygon(session: AsyncSession, polygon: UserPolygon, payload: PolygonUpdate, user_id: uuid.UUID | None = None) -> PolygonRead:
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_updated_at", None)
    if not _same_version(polygon.updated_at, expected):
        raise RuntimeError("POLYGON_VERSION_CONFLICT")
    geometry_changed = "geometry" in data
    if "area_size" in data:
        area_size = data.pop("area_size")
        properties = dict(polygon.properties or {})
        if area_size is None:
            properties.pop("size", None)
        else:
            properties["size"] = area_size
        polygon.properties = properties
    if "geometry" in data and payload.geometry is not None:
        polygon.geometry = to_wkb_element(payload.geometry)
        data.pop("geometry")
    for key, value in data.items():
        setattr(polygon, key, value)
    polygon.updated_by_user_id = user_id
    polygon.updated_at = utcnow()
    await session.commit()
    await session.refresh(polygon)
    if geometry_changed:
        await enrich_polygon_address(session, polygon)
        await refresh_polygon_area_assignments(session, polygon.id)
        await session.commit()
    return serialize_polygon(polygon)


async def update_polygon_verwaltung(
    session: AsyncSession,
    polygon: UserPolygon,
    payload: PolygonVerwaltungUpdate,
    user_id: uuid.UUID,
) -> PolygonVerwaltungRead:
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_updated_at", None)
    if not _same_version(polygon.updated_at, expected):
        raise RuntimeError("POLYGON_VERSION_CONFLICT")
    for key, value in data.items():
        setattr(polygon, key, value)
    if "occupancy_status" in data:
        polygon.occupancy_source = "MANUAL"
        polygon.occupancy_source_tag = None
        polygon.occupancy_source_updated_at = utcnow()
    polygon.updated_by_user_id = user_id
    polygon.updated_at = utcnow()
    await session.commit()
    await session.refresh(polygon)
    logger.info(
        "Polygon management fields changed polygon_id=%s user_id=%s fields=%s",
        polygon.uuid,
        user_id,
        sorted(data),
    )
    return await polygon_verwaltung_detail(session, polygon)


async def delete_polygon(
    session: AsyncSession,
    polygon: UserPolygon,
    deleted_by_user_id: uuid.UUID,
) -> None:
    polygon_id = polygon.uuid
    await session.delete(polygon)
    await session.commit()
    logger.info(
        "Polygon deleted polygon_id=%s deleted_by_user_id=%s",
        polygon_id,
        deleted_by_user_id,
    )


async def polygons_geojson(session: AsyncSession) -> FeatureCollection:
    polygons = await list_polygons(session)
    return FeatureCollection(
        type="FeatureCollection",
        features=[
            Feature(
                type="Feature",
                id=polygon.id,
                geometry=polygon.geometry,
                properties={
                    **polygon.properties,
                    "id": polygon.id,
                    "slug": polygon.slug,
                    "name": polygon.name,
                    "category": polygon.category,
                    "created_by_user_id": polygon.created_by_user_id,
                },
            )
            for polygon in polygons
        ],
    )


async def polygon_metrics(session: AsyncSession, polygon_id: uuid.UUID) -> PolygonMetrics | None:
    row = await session.execute(
        select(
            func.ST_Area(func.ST_Transform(UserPolygon.geometry, METRIC_SRID)).label("area_m2"),
            func.ST_Perimeter(func.ST_Transform(UserPolygon.geometry, METRIC_SRID)).label("perimeter_m"),
            func.ST_X(func.ST_Centroid(UserPolygon.geometry)).label("centroid_lng"),
            func.ST_Y(func.ST_Centroid(UserPolygon.geometry)).label("centroid_lat"),
            func.ST_XMin(func.ST_Envelope(UserPolygon.geometry)).label("min_lng"),
            func.ST_YMin(func.ST_Envelope(UserPolygon.geometry)).label("min_lat"),
            func.ST_XMax(func.ST_Envelope(UserPolygon.geometry)).label("max_lng"),
            func.ST_YMax(func.ST_Envelope(UserPolygon.geometry)).label("max_lat"),
        ).where(UserPolygon.uuid == polygon_id)
    )
    metrics: Any = row.mappings().first()
    if metrics is None:
        return None
    return PolygonMetrics(
        area_m2=float(metrics["area_m2"]),
        perimeter_m=float(metrics["perimeter_m"]),
        centroid=(float(metrics["centroid_lng"]), float(metrics["centroid_lat"])),
        bbox=(float(metrics["min_lng"]), float(metrics["min_lat"]), float(metrics["max_lng"]), float(metrics["max_lat"])),
    )

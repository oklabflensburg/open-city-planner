import logging
import uuid
from collections.abc import Mapping
from typing import Any, Literal

from geoalchemy2.shape import from_shape
from pydantic import TypeAdapter
from shapely.geometry import shape
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.polygon_osm_source import PolygonOsmSource
from app.models.user_polygon import UserPolygon
from app.schemas.geojson import AreaGeometry
from app.schemas.osm import OsmPolygonImportRead, OsmPolygonImportRequest
from app.services.geometry import to_wkb_element
from app.services.gis_mutations import invalidate_gis_after_mutation
from app.services.notification_policy import DomainEvent, NotificationEventType
from app.services.notifications import notify_users, publish_notifications
from app.services.osm_canonical import osm_business_category, osm_floor_group
from app.services.osm_exclusions import should_exclude_osm_feature
from app.services.osm_features import clear_viewport_cache
from app.services.osm_occupancy import detect_osm_occupancy_status
from app.services.polygons import (
    enrich_polygon_address,
    generate_unique_polygon_slug,
    polygon_slug_source,
)
from app.services.social_publishing import enqueue_polygon_adoption

logger = logging.getLogger(__name__)
_area_adapter = TypeAdapter(AreaGeometry)

SOURCE_SQL = text("""
SELECT osm_type, osm_id, tags, imported_at, ST_Dimension(geometry) AS dimension,
       ST_AsGeoJSON(geometry, 7)::json AS geometry
FROM osm_features
WHERE osm_type = :osm_type AND osm_id = :osm_id
""")

CONTAINER_SQL = text("""
WITH source AS (
  SELECT geometry, tags FROM osm_features
  WHERE osm_type = :osm_type AND osm_id = :osm_id AND ST_Dimension(geometry) = 0
)
SELECT candidate.osm_type, candidate.osm_id, candidate.tags, candidate.imported_at,
       ST_AsGeoJSON(candidate.geometry, 7)::json AS geometry
FROM osm_features candidate CROSS JOIN source
WHERE candidate.geometry && source.geometry
  AND ST_Dimension(candidate.geometry) = 2
  AND ST_IsValid(candidate.geometry)
  AND ST_Covers(candidate.geometry, source.geometry)
  AND candidate.tags->>'natural' IS DISTINCT FROM 'peninsula'
  AND (candidate.tags ? 'building' OR candidate.tags ? 'shop' OR candidate.tags ? 'amenity')
ORDER BY
  (NULLIF(lower(candidate.tags->>'name'), '') = NULLIF(lower(source.tags->>'name'), '')) DESC,
  (candidate.tags->>'shop' = source.tags->>'shop') DESC,
  (candidate.tags->>'amenity' = source.tags->>'amenity') DESC,
  ST_Area(ST_Transform(candidate.geometry, 25832)) ASC,
  candidate.osm_type, candidate.osm_id
LIMIT 1
""")

EXISTING_SQL = text("""
SELECT polygon.uuid::text AS id, polygon.slug, polygon.name, polygon.floor
FROM polygon_osm_sources source
JOIN user_polygons polygon ON polygon.id = source.polygon_id
WHERE source.osm_type = :osm_type AND source.osm_id = :osm_id
  AND polygon.floor IS NOT DISTINCT FROM :floor
LIMIT 1
""")

SNAPSHOT_TAGS = (
    "name",
    "shop",
    "amenity",
    "office",
    "craft",
    "tourism",
    "brand",
    "operator",
    "opening_hours",
    "website",
    "phone",
    "addr:street",
    "addr:housenumber",
    "addr:postcode",
    "addr:city",
    "level",
    "building",
    "building:levels",
    "disused",
    "disused:shop",
    "abandoned",
    "abandoned:shop",
    "wikidata",
    "wikipedia",
)


class OsmImportNotFound(LookupError):
    pass


class OsmImportGeometryRequired(ValueError):
    pass


class OsmImportNotImportable(ValueError):
    pass


class OsmImportAlreadyExists(ValueError):
    def __init__(self, *, polygon_id: str, slug: str) -> None:
        self.polygon_id = polygon_id
        self.slug = slug
        super().__init__("OSM feature already imported for this floor")


def _text(tags: Mapping[str, Any], key: str) -> str | None:
    value = tags.get(key)
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def map_osm_category(tags: Mapping[str, Any]) -> str:
    return osm_business_category(tags) or "otherAreas"


def map_osm_floor(tags: Mapping[str, Any], requested: str | None) -> str | None:
    if requested:
        return requested
    group = osm_floor_group(tags)
    if group == "OG":
        level = _text(tags, "level")
        return f"{int(level)}OG" if level and level.isdigit() else "OG"
    return group


def _snapshot(tags: Mapping[str, Any]) -> dict[str, str]:
    return {key: value for key in SNAPSHOT_TAGS if (value := _text(tags, key)) is not None}


async def create_polygon_from_osm(
    session: AsyncSession,
    payload: OsmPolygonImportRequest,
    user_id: uuid.UUID,
) -> OsmPolygonImportRead:
    source = (
        (
            await session.execute(
                SOURCE_SQL, {"osm_type": payload.osm_type, "osm_id": payload.osm_id}
            )
        )
        .mappings()
        .first()
    )
    if source is None:
        raise OsmImportNotFound

    tags = source["tags"] or {}
    if should_exclude_osm_feature(tags):
        raise OsmImportNotImportable("natural=peninsula is not importable")
    geometry_source: Literal["osm_feature", "containing_osm_area", "manual"]
    geometry_source_row: Mapping[str, Any] | None = None
    if source["dimension"] == 2:
        geometry_data = source["geometry"]
        geometry_source = "osm_feature"
    elif payload.geometry is not None:
        geometry_data = payload.geometry.model_dump()
        geometry_source = "manual"
    else:
        container = (
            (
                await session.execute(
                    CONTAINER_SQL, {"osm_type": payload.osm_type, "osm_id": payload.osm_id}
                )
            )
            .mappings()
            .first()
        )
        if container is None:
            raise OsmImportGeometryRequired
        geometry_data = container["geometry"]
        geometry_source_row = container
        geometry_source = "containing_osm_area"

    geometry = _area_adapter.validate_python(geometry_data)
    occupancy = detect_osm_occupancy_status(tags)
    floor = map_osm_floor(tags, payload.floor)
    existing = (
        (
            await session.execute(
                EXISTING_SQL,
                {
                    "osm_type": payload.osm_type,
                    "osm_id": payload.osm_id,
                    "floor": floor,
                },
            )
        )
        .mappings()
        .first()
    )
    if existing:
        raise OsmImportAlreadyExists(polygon_id=existing["id"], slug=existing["slug"])
    polygon_uuid = uuid.uuid4()
    title = _text(tags, "name") or "Neue Fläche"
    address_parts = [
        " ".join(filter(None, [_text(tags, "addr:street"), _text(tags, "addr:housenumber")])),
        " ".join(filter(None, [_text(tags, "addr:postcode"), _text(tags, "addr:city")])),
    ]
    display_address = ", ".join(part for part in address_parts if part) or None
    polygon = UserPolygon(
        uuid=polygon_uuid,
        name=title,
        slug=await generate_unique_polygon_slug(session, title),
        floor=floor,
        category=map_osm_category(tags),
        geometry=to_wkb_element(geometry),
        properties={
            key: value
            for key, value in {
                "osm_brand": _text(tags, "brand"),
                "osm_operator": _text(tags, "operator"),
                "osm_opening_hours": _text(tags, "opening_hours"),
                "previous_osm_shop_type": occupancy.previous_shop_type,
            }.items()
            if value is not None
        },
        address_display_name=display_address,
        address_street=_text(tags, "addr:street"),
        address_house_number=_text(tags, "addr:housenumber"),
        address_postal_code=_text(tags, "addr:postcode"),
        address_city=_text(tags, "addr:city"),
        address_lookup_status="resolved" if display_address else "pending",
        occupancy_status=occupancy.status,
        occupancy_source="OSM" if occupancy.status == "VACANT" else "UNKNOWN",
        occupancy_source_tag=occupancy.source_tag,
        occupancy_source_updated_at=source["imported_at"] if occupancy.source_tag else None,
        business_structure="UNKNOWN",
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    session.add(polygon)
    await session.flush()
    session.add(
        PolygonOsmSource(
            polygon_id=polygon.id,
            osm_type=payload.osm_type,
            osm_id=payload.osm_id,
            is_primary=True,
            osm_snapshot=_snapshot(tags),
            source_geometry=from_shape(shape(source["geometry"]), srid=4326),
            source_updated_at=source["imported_at"],
        )
    )
    if geometry_source_row is not None:
        session.add(
            PolygonOsmSource(
                polygon_id=polygon.id,
                osm_type=geometry_source_row["osm_type"],
                osm_id=geometry_source_row["osm_id"],
                is_primary=False,
                osm_snapshot=_snapshot(geometry_source_row["tags"] or {}),
                source_geometry=from_shape(shape(geometry_source_row["geometry"]), srid=4326),
                source_updated_at=geometry_source_row["imported_at"],
            )
        )
    await enqueue_polygon_adoption(
        session,
        polygon,
        osm_type=payload.osm_type,
        osm_id=payload.osm_id,
    )
    await session.commit()
    await session.refresh(polygon)
    if display_address is None and await enrich_polygon_address(session, polygon):
        polygon.slug = await generate_unique_polygon_slug(session, polygon_slug_source(polygon))
        await session.commit()
        await session.refresh(polygon)
    await invalidate_gis_after_mutation(session)
    notifications = await notify_users(
        session,
        [user_id],
        DomainEvent(
            event_type=NotificationEventType.GIS_AREA_ADOPTED_FROM_OSM,
            actor_user_id=user_id,
            resource_type="POLYGON",
            resource_id=str(polygon.uuid),
            resource_slug=polygon.slug,
            resource_title=polygon.name,
            metadata={"osm_type": payload.osm_type, "osm_id": payload.osm_id},
        ),
        allow_self=True,
    )
    await session.commit()
    publish_notifications(notifications)
    clear_viewport_cache()
    logger.info(
        "POLYGON_CREATED_FROM_OSM polygon_id=%s source=%s/%s user_id=%s",
        polygon.uuid,
        payload.osm_type,
        payload.osm_id,
        user_id,
    )
    return OsmPolygonImportRead(
        id=str(polygon.uuid),
        slug=polygon.slug,
        geometry_source=geometry_source,
        source_osm_type=payload.osm_type,
        source_osm_id=payload.osm_id,
        occupancy_status=polygon.occupancy_status,
        occupancy_source=polygon.occupancy_source,
    )

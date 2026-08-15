from collections import Counter
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key, viewport_tile_bucket
from app.cache.service import cache_service
from app.core.config import get_settings
from app.schemas.osm import (
    OsmObjectInfo,
    OsmViewportFeature,
    OsmViewportFeatureCollection,
    OsmViewportMeta,
    OsmViewportProperties,
    OsmViewportQuery,
)
from app.services.cache_versions import cache_version
from app.services.osm_exclusions import should_exclude_osm_feature
from app.services.osm_lookup import normalize_osm_tags
from app.services.osm_occupancy import detect_osm_occupancy_status
from app.services.poi_categories import OSM_FEATURE_CATEGORIES, OSM_FEATURE_CATEGORY_SQL

OSM_VIEWPORT_CACHE_RESOURCE = "osm:viewport:v2"

VIEWPORT_SQL = text(f"""
WITH bounds AS (
  SELECT ST_MakeEnvelope(:west, :south, :east, :north, 4326) AS geometry
), categorized AS (
  SELECT osm.osm_type, osm.osm_id, osm.tags, osm.geometry, osm.imported_at,
         ST_Dimension(osm.geometry) AS dimension,
         {OSM_FEATURE_CATEGORY_SQL} AS category
  FROM osm_features osm CROSS JOIN bounds
  WHERE osm.geometry && bounds.geometry
    AND ST_Intersects(osm.geometry, bounds.geometry)
    AND ST_IsValid(osm.geometry)
    AND osm.tags->>'natural' IS DISTINCT FROM 'peninsula'
), selected AS (
  SELECT *,
    CASE
      WHEN dimension = 0 THEN geometry
      WHEN :zoom < 15 THEN ST_SimplifyPreserveTopology(geometry, 0.00005)
      WHEN :zoom < 17 THEN ST_SimplifyPreserveTopology(geometry, 0.00001)
      ELSE geometry
    END AS output_geometry
  FROM categorized
  WHERE category IS NOT NULL
    AND (cardinality(CAST(:categories AS text[])) = 0 OR category = ANY(CAST(:categories AS text[])))
    AND (:include_buildings OR category <> 'building')
    AND (:zoom >= 17 OR category <> 'building')
    AND (:zoom >= 15 OR category NOT IN ('building', 'landuse'))
    AND (:zoom >= 13 OR (tags ? 'name' AND category NOT IN ('building', 'landuse')))
), ranked AS (
  SELECT *,
         CASE WHEN dimension = 0 THEN 'point'
              WHEN category = 'building' THEN 'building'
              ELSE 'polygon' END AS feature_group,
         ROW_NUMBER() OVER (
           PARTITION BY CASE WHEN dimension = 0 THEN 'point'
                             WHEN category = 'building' THEN 'building'
                             ELSE 'polygon' END
           ORDER BY (tags ? 'name') DESC, category, osm_type, osm_id
         ) AS group_rank
  FROM selected
), limited AS (
  SELECT * FROM ranked
  WHERE (feature_group = 'point' AND group_rank <= :point_limit)
     OR (feature_group = 'polygon' AND group_rank <= :polygon_limit)
     OR (feature_group = 'building' AND group_rank <= :building_limit)
)
SELECT selected.osm_type, selected.osm_id, selected.tags, selected.category,
       selected.dimension, selected.imported_at,
       COALESCE(linked.polygons, '[]'::json) AS linked_polygons,
       ST_AsGeoJSON(output_geometry, 6)::json AS geometry,
       COALESCE(tags->>'shop', tags->>'amenity', tags->>'office', tags->>'craft',
                tags->>'tourism', tags->>'leisure', tags->>'healthcare',
                tags->>'public_transport', tags->>'building', tags->>'landuse',
                tags->>'natural') AS primary_type
FROM limited selected
LEFT JOIN LATERAL (
  SELECT json_agg(json_build_object(
    'id', polygon.uuid::text, 'slug', polygon.slug, 'name', polygon.name, 'floor', polygon.floor
  ) ORDER BY polygon.floor NULLS FIRST, polygon.name) AS polygons
  FROM polygon_osm_sources source
  JOIN user_polygons polygon ON polygon.id = source.polygon_id
  WHERE source.osm_type = selected.osm_type AND source.osm_id = selected.osm_id
) linked ON true
ORDER BY (dimension = 0) DESC, (tags ? 'name') DESC, category, osm_type, osm_id
""")

# Kept as an empty compatibility object for older callers; shared caching lives in Redis.
_cache: dict = {}

DETAIL_SQL = text("""
SELECT osm_type, osm_id, tags,
       ST_X(ST_PointOnSurface(geometry)) AS longitude,
       ST_Y(ST_PointOnSurface(geometry)) AS latitude
FROM osm_features
WHERE osm_type = :osm_type AND osm_id = :osm_id
""")

def clear_viewport_cache() -> None:
    """Compatibility hook; shared cache invalidation is version based."""


def selected_categories(value: str | None) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(part.strip() for part in (value or "").split(",") if part.strip()))
    invalid = set(values) - OSM_FEATURE_CATEGORIES
    if invalid:
        raise ValueError("invalid OSM feature category")
    return values


def osm_viewport_cache_params(query: OsmViewportQuery, categories: Sequence[str]) -> dict:
    bucket = viewport_tile_bucket(query.west, query.south, query.east, query.north, query.zoom)
    return {
        "tile_zoom": bucket["tile_zoom"],
        "x_range": [bucket["x_min"], bucket["x_max"]],
        "y_range": [bucket["y_min"], bucket["y_max"]],
        "zoom": round(query.zoom, 1),
        "categories": sorted(categories),
        "buildings": query.buildings,
        "limit": query.limit,
    }


async def viewport_features_json(
    session: AsyncSession, query: OsmViewportQuery
) -> bytes:
    categories = selected_categories(query.categories)
    if query.zoom < 11:
        return OsmViewportFeatureCollection(
            features=[], meta=OsmViewportMeta(count=0, truncated=False, zoom=query.zoom, summary={})
        ).model_dump_json().encode()
    settings = get_settings()
    zoom_limit = (
        settings.osm_viewport_low_zoom_feature_limit
        if query.zoom < 15
        else settings.osm_viewport_mid_zoom_feature_limit
        if query.zoom < 17
        else settings.osm_viewport_feature_limit
    )
    limit = min(query.limit, settings.osm_viewport_feature_limit, zoom_limit)
    if query.zoom < 15:
        point_limit, polygon_limit, building_limit = limit, 0, 0
    elif query.zoom < 17:
        polygon_limit = min(settings.osm_viewport_polygon_feature_limit, limit // 6)
        point_limit, building_limit = limit - polygon_limit, 0
    else:
        building_limit = (
            min(settings.osm_viewport_building_feature_limit, limit // 10)
            if query.buildings and limit >= 10
            else 0
        )
        polygon_limit = min(
            settings.osm_viewport_polygon_feature_limit,
            max(1, limit // 5) if limit > building_limit + 1 else 0,
        )
        point_limit = min(
            settings.osm_viewport_point_feature_limit,
            limit - polygon_limit - building_limit,
        )
    bucket = viewport_tile_bucket(query.west, query.south, query.east, query.north, query.zoom)
    version = await cache_version(session, "osm")
    key = build_cache_key(
        OSM_VIEWPORT_CACHE_RESOURCE, osm_viewport_cache_params(query, categories), version=version
    )

    async def compute() -> bytes:
        rows = (
            await session.execute(
                VIEWPORT_SQL,
                {
                    "west": bucket["west"],
                    "south": bucket["south"],
                    "east": bucket["east"],
                    "north": bucket["north"],
                    "zoom": query.zoom,
                    "categories": list(categories),
                    "include_buildings": query.buildings,
                    "point_limit": point_limit + 1,
                    "polygon_limit": polygon_limit + 1,
                    "building_limit": building_limit + 1,
                },
            )
        ).mappings().all()
        # Defense in depth for alternate repositories and mocked/custom row providers.
        rows = [row for row in rows if not should_exclude_osm_feature(row["tags"] or {})]
        truncated = (
            sum(row["dimension"] == 0 for row in rows) > point_limit
            or sum(row["category"] == "building" for row in rows) > building_limit
            or sum(row["dimension"] != 0 and row["category"] != "building" for row in rows)
            > polygon_limit
        )
        kept = {"point": 0, "polygon": 0, "building": 0}
        limited_rows = []
        for row in rows:
            group = (
                "point"
                if row["dimension"] == 0
                else "building"
                if row["category"] == "building"
                else "polygon"
            )
            group_limit = {
                "point": point_limit,
                "polygon": polygon_limit,
                "building": building_limit,
            }[group]
            if kept[group] < group_limit:
                kept[group] += 1
                limited_rows.append(row)
        rows = limited_rows
        features = []
        for row in rows:
            occupancy = detect_osm_occupancy_status(row["tags"] or {})
            features.append(
                OsmViewportFeature(
                    id=f"{row['osm_type']}/{row['osm_id']}",
                    geometry=row["geometry"],
                    properties=OsmViewportProperties(
                        feature_id=f"{row['osm_type']}/{row['osm_id']}",
                        osm_type=row["osm_type"],
                        osm_id=row["osm_id"],
                        category=row["category"],
                        name=(row["tags"] or {}).get("name"),
                        primary_type=row["primary_type"],
                        natural=(row["tags"] or {}).get("natural"),
                        feature_type="point" if row["dimension"] == 0 else "polygon",
                        occupancy_status=occupancy.status,
                        occupancy_source="OSM" if occupancy.status == "VACANT" else None,
                        stadtplaner=row.get("linked_polygons") or [],
                    ),
                )
            )
        summary = dict(Counter(feature.properties.category for feature in features))
        dates = [row["imported_at"] for row in rows if row["imported_at"] is not None]
        return OsmViewportFeatureCollection(
            features=features,
            meta=OsmViewportMeta(
                count=len(features),
                truncated=truncated,
                zoom=query.zoom,
                summary=summary,
                osm_data_updated_at=max(dates) if dates else None,
            ),
        ).model_dump_json().encode()

    data, _status = await cache_service.get_or_compute_bytes(
        key,
        ttl=settings.osm_viewport_cache_ttl,
        resource="osm-viewport",
        compute=compute,
    )
    return data


async def viewport_features(
    session: AsyncSession, query: OsmViewportQuery
) -> OsmViewportFeatureCollection:
    return OsmViewportFeatureCollection.model_validate_json(
        await viewport_features_json(session, query)
    )


async def osm_feature_detail(
    session: AsyncSession, *, osm_type: str, osm_id: int
) -> OsmObjectInfo | None:
    row = (await session.execute(DETAIL_SQL, {"osm_type": osm_type, "osm_id": osm_id})).mappings().first()
    if row is None:
        return None
    return normalize_osm_tags(
        osm_type=row["osm_type"], osm_id=row["osm_id"], tags=row["tags"] or {},
        longitude=float(row["longitude"]), latitude=float(row["latitude"]),
    )

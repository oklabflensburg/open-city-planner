import time
from collections import Counter
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.osm import (
    OsmObjectInfo,
    OsmViewportFeature,
    OsmViewportFeatureCollection,
    OsmViewportMeta,
    OsmViewportProperties,
    OsmViewportQuery,
)
from app.services.osm_lookup import normalize_osm_tags
from app.services.osm_occupancy import detect_osm_occupancy_status
from app.services.poi_categories import OSM_FEATURE_CATEGORIES, OSM_FEATURE_CATEGORY_SQL

VIEWPORT_SQL = text(f"""
WITH bounds AS (
  SELECT ST_MakeEnvelope(:west, :south, :east, :north, 4326) AS geometry
), categorized AS (
  SELECT osm.osm_type, osm.osm_id, osm.tags, osm.geometry, osm.imported_at,
         COALESCE(linked.polygons, '[]'::json) AS linked_polygons,
         ST_Dimension(osm.geometry) AS dimension,
         {OSM_FEATURE_CATEGORY_SQL} AS category
  FROM osm_features osm CROSS JOIN bounds
  LEFT JOIN LATERAL (
    SELECT json_agg(json_build_object(
      'id', polygon.uuid::text, 'slug', polygon.slug, 'name', polygon.name, 'floor', polygon.floor
    ) ORDER BY polygon.floor NULLS FIRST, polygon.name) AS polygons
    FROM polygon_osm_sources source
    JOIN user_polygons polygon ON polygon.id = source.polygon_id
    WHERE source.osm_type = osm.osm_type AND source.osm_id = osm.osm_id
  ) linked ON true
  WHERE osm.geometry && bounds.geometry
    AND ST_Intersects(osm.geometry, bounds.geometry)
    AND ST_IsValid(osm.geometry)
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
)
SELECT osm_type, osm_id, tags, category, dimension, imported_at, linked_polygons,
       ST_AsGeoJSON(output_geometry, 6)::json AS geometry,
       COALESCE(tags->>'shop', tags->>'amenity', tags->>'office', tags->>'craft',
                tags->>'tourism', tags->>'leisure', tags->>'healthcare',
                tags->>'public_transport', tags->>'building', tags->>'landuse',
                tags->>'natural') AS primary_type
FROM selected
ORDER BY (dimension = 0) DESC, (tags ? 'name') DESC, category, osm_type, osm_id
LIMIT :row_limit
""")

DETAIL_SQL = text("""
SELECT osm_type, osm_id, tags,
       ST_X(ST_PointOnSurface(geometry)) AS longitude,
       ST_Y(ST_PointOnSurface(geometry)) AS latitude
FROM osm_features
WHERE osm_type = :osm_type AND osm_id = :osm_id
""")

_cache: dict[tuple[object, ...], tuple[float, OsmViewportFeatureCollection]] = {}


def clear_viewport_cache() -> None:
    _cache.clear()


def selected_categories(value: str | None) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(part.strip() for part in (value or "").split(",") if part.strip()))
    invalid = set(values) - OSM_FEATURE_CATEGORIES
    if invalid:
        raise ValueError("invalid OSM feature category")
    return values


def _cache_key(query: OsmViewportQuery, categories: Sequence[str]) -> tuple[object, ...]:
    return (
        round(query.west, 5), round(query.south, 5), round(query.east, 5), round(query.north, 5),
        round(query.zoom, 1), tuple(categories), query.buildings, query.limit,
    )


async def viewport_features(
    session: AsyncSession, query: OsmViewportQuery
) -> OsmViewportFeatureCollection:
    categories = selected_categories(query.categories)
    if query.zoom < 11:
        return OsmViewportFeatureCollection(
            features=[], meta=OsmViewportMeta(count=0, truncated=False, zoom=query.zoom, summary={})
        )
    settings = get_settings()
    limit = min(query.limit, settings.osm_viewport_feature_limit)
    key = _cache_key(query, categories)
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    rows = (await session.execute(VIEWPORT_SQL, {
        "west": query.west, "south": query.south, "east": query.east, "north": query.north,
        "zoom": query.zoom, "categories": list(categories), "include_buildings": query.buildings,
        "row_limit": limit + 1,
    })).mappings().all()
    truncated = len(rows) > limit
    rows = rows[:limit]
    features = []
    for row in rows:
        occupancy = detect_osm_occupancy_status(row["tags"] or {})
        features.append(OsmViewportFeature(
            id=f"{row['osm_type']}/{row['osm_id']}",
            geometry=row["geometry"],
            properties=OsmViewportProperties(
                feature_id=f"{row['osm_type']}/{row['osm_id']}",
                osm_type=row["osm_type"], osm_id=row["osm_id"], category=row["category"],
                name=(row["tags"] or {}).get("name"), primary_type=row["primary_type"],
                feature_type="point" if row["dimension"] == 0 else "polygon",
                occupancy_status=occupancy.status,
                occupancy_source="OSM" if occupancy.status == "VACANT" else None,
                stadtplanner=row.get("linked_polygons") or [],
            ),
        ))
    summary = dict(Counter(feature.properties.category for feature in features))
    dates = [row["imported_at"] for row in rows if row["imported_at"] is not None]
    result = OsmViewportFeatureCollection(
        features=features,
        meta=OsmViewportMeta(
            count=len(features), truncated=truncated, zoom=query.zoom, summary=summary,
            osm_data_updated_at=max(dates) if dates else None,
        ),
    )
    if len(_cache) >= 128:
        oldest = min(_cache, key=lambda item: _cache[item][0])
        _cache.pop(oldest, None)
    _cache[key] = (time.monotonic() + settings.osm_viewport_cache_ttl_seconds, result)
    return result


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

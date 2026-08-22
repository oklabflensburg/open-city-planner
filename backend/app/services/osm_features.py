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
from app.schemas.polygon_filters import PolygonFilterParams
from app.services.cache_versions import cache_version
from app.services.external_links import external_links_from_osm_tags
from app.services.osm_canonical import (
    osm_business_category,
    osm_business_category_sql,
    osm_floor_group,
    osm_floor_group_sql,
    osm_status_sql,
)
from app.services.osm_exclusions import should_exclude_osm_feature
from app.services.osm_lookup import normalize_osm_tags
from app.services.osm_occupancy import detect_osm_occupancy_status
from app.services.poi_categories import (
    AREA_POI_CATEGORY_SQL,
    OSM_FEATURE_CATEGORIES,
    OSM_FEATURE_CATEGORY_SQL,
)

OSM_VIEWPORT_CACHE_RESOURCE = "osm:viewport:v5"

CANONICAL_CATEGORY_SQL = osm_business_category_sql()
CANONICAL_FLOOR_SQL = osm_floor_group_sql()
CANONICAL_STATUS_SQL = osm_status_sql()

VIEWPORT_SQL = text(f"""
WITH bounds AS (
  SELECT ST_MakeEnvelope(:west, :south, :east, :north, 4326) AS geometry
), target_area AS (
  SELECT geometry FROM analysis_areas WHERE slug = CAST(:analysis_area AS text)
), categorized AS (
  SELECT osm.osm_type, osm.osm_id, osm.tags, osm.geometry, osm.imported_at,
         ST_Dimension(osm.geometry) AS dimension,
         {OSM_FEATURE_CATEGORY_SQL} AS category,
         {CANONICAL_CATEGORY_SQL} AS canonical_category,
         {CANONICAL_FLOOR_SQL} AS canonical_floor,
         {CANONICAL_STATUS_SQL} AS canonical_status,
         CASE WHEN ST_Dimension(osm.geometry) = 2
           THEN ST_Area(ST_Transform(osm.geometry, 25832)) END AS mapped_area_m2,
         EXISTS (
           SELECT 1 FROM polygon_osm_sources source
           WHERE source.osm_type = osm.osm_type AND source.osm_id = osm.osm_id
         ) AS is_linked
  FROM osm_features osm CROSS JOIN bounds
  WHERE osm.geometry && bounds.geometry
    AND ST_Intersects(osm.geometry, bounds.geometry)
    AND (CAST(:analysis_area AS text) IS NULL OR EXISTS (
      SELECT 1 FROM target_area area
      WHERE osm.geometry && area.geometry
        AND ST_Covers(area.geometry, ST_PointOnSurface(osm.geometry))
    ))
    AND (CAST(:poi_category AS text) IS NULL OR ({AREA_POI_CATEGORY_SQL}) = CAST(:poi_category AS text))
    AND ST_IsValid(osm.geometry)
    AND osm.tags->>'natural' IS DISTINCT FROM 'peninsula'
), facet_counts AS (
  SELECT canonical_category, count(*) AS count
  FROM categorized
  WHERE (NOT :deduplicate_linked OR NOT is_linked) AND canonical_category IS NOT NULL
    AND (cardinality(CAST(:floors AS text[])) = 0 OR canonical_floor = ANY(CAST(:floors AS text[])))
    AND (cardinality(CAST(:statuses AS text[])) = 0 OR canonical_status = ANY(CAST(:statuses AS text[])))
    AND cardinality(CAST(:area_sizes AS text[])) = 0
    AND cardinality(CAST(:business_structures AS text[])) = 0
  GROUP BY canonical_category
), facets AS (
  SELECT COALESCE(jsonb_object_agg(canonical_category, count), '{{}}'::jsonb) AS canonical_facets
  FROM facet_counts
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
    AND (NOT :deduplicate_linked OR NOT is_linked)
    AND (cardinality(CAST(:osm_categories AS text[])) = 0 OR category = ANY(CAST(:osm_categories AS text[])))
    AND (canonical_category IS NULL OR (
      (cardinality(CAST(:gis_categories AS text[])) = 0 OR canonical_category = ANY(CAST(:gis_categories AS text[])))
      AND (cardinality(CAST(:floors AS text[])) = 0 OR canonical_floor = ANY(CAST(:floors AS text[])))
      AND (cardinality(CAST(:statuses AS text[])) = 0 OR canonical_status = ANY(CAST(:statuses AS text[])))
      AND cardinality(CAST(:area_sizes AS text[])) = 0
      AND cardinality(CAST(:business_structures AS text[])) = 0
    ))
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
       selected.canonical_category, selected.canonical_floor, selected.canonical_status,
       selected.mapped_area_m2, selected.dimension, selected.imported_at,
       (SELECT count(*) FROM categorized WHERE is_linked) AS deduplicated_linked_count,
       facets.canonical_facets,
       COALESCE(linked.polygons, '[]'::json) AS linked_polygons,
       ST_AsGeoJSON(output_geometry, 6)::json AS geometry,
       COALESCE(tags->>'shop', tags->>'amenity', tags->>'office', tags->>'craft',
                tags->>'tourism', tags->>'leisure', tags->>'healthcare',
                tags->>'public_transport', tags->>'building', tags->>'landuse',
                tags->>'natural') AS primary_type
FROM facets
LEFT JOIN limited selected ON true
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


def osm_viewport_cache_params(
    query: OsmViewportQuery, categories: Sequence[str], filters: PolygonFilterParams | None = None
) -> dict:
    filters = filters or PolygonFilterParams()
    bucket = viewport_tile_bucket(query.west, query.south, query.east, query.north, query.zoom)
    return {
        "tile_zoom": bucket["tile_zoom"],
        "x_range": [bucket["x_min"], bucket["x_max"]],
        "y_range": [bucket["y_min"], bucket["y_max"]],
        "zoom": round(query.zoom, 1),
        "categories": sorted(categories),
        "analysis_area": query.analysis_area,
        "poi_category": query.poi_category,
        "buildings": query.buildings,
        "limit": query.limit,
        "filters": filters.cache_params(),
    }


def _matches_business_filters(
    tags: dict, filters: PolygonFilterParams, category: str | None
) -> bool:
    if category is None:
        return True
    if filters.categories and category not in filters.categories:
        return False
    floor = osm_floor_group(tags)
    if filters.floors and floor not in filters.floors:
        return False
    status = detect_osm_occupancy_status(tags).status
    if filters.occupancy_statuses and status not in filters.occupancy_statuses:
        return False
    # OSM has neither a reliable sales-area class nor a maintained business structure.
    return not filters.area_sizes and not filters.business_structures


async def viewport_features_json(
    session: AsyncSession, query: OsmViewportQuery,
    filters: PolygonFilterParams | None = None,
) -> bytes:
    filters = filters or PolygonFilterParams()
    categories = selected_categories(query.osm_categories)
    explicitly_empty = any(
        value == ("NONE",)
        for value in (
            filters.categories, filters.floors, filters.area_sizes,
            filters.occupancy_statuses, filters.business_structures,
        )
    )
    if explicitly_empty or (filters.sources and "OSM" not in filters.sources):
        return OsmViewportFeatureCollection(
            features=[], meta=OsmViewportMeta(count=0, truncated=False, zoom=query.zoom, summary={})
        ).model_dump_json().encode()
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
        OSM_VIEWPORT_CACHE_RESOURCE,
        osm_viewport_cache_params(query, categories, filters), version=version,
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
                    "analysis_area": query.analysis_area,
                    "poi_category": query.poi_category,
                    "osm_categories": list(categories),
                    "gis_categories": list(filters.categories),
                    "floors": list(filters.floors),
                    "statuses": list(filters.occupancy_statuses),
                    "area_sizes": list(filters.area_sizes),
                    "business_structures": list(filters.business_structures),
                    "deduplicate_linked": not filters.sources or "STADTPLANNER" in filters.sources,
                    "include_buildings": query.buildings,
                    "point_limit": point_limit + 1,
                    "polygon_limit": polygon_limit + 1,
                    "building_limit": building_limit + 1,
                },
            )
        ).mappings().all()
        # Defense in depth for alternate repositories and mocked/custom row providers.
        facet_counts = next(
            (dict(row.get("canonical_facets") or {}) for row in rows if row.get("canonical_facets") is not None),
            {},
        )
        deduplicate_linked = not filters.sources or "STADTPLANNER" in filters.sources
        linked_count = max(
            (int(row.get("deduplicated_linked_count") or 0) for row in rows), default=0
        ) if deduplicate_linked else 0
        rows = [row for row in rows if row.get("osm_id") is not None]
        rows = [
            row for row in rows
            if not should_exclude_osm_feature(row["tags"] or {})
            and (not deduplicate_linked or not row.get("linked_polygons"))
            and _matches_business_filters(
                row["tags"] or {}, filters,
                row.get("canonical_category") or osm_business_category(row["tags"] or {}),
            )
        ]
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
            canonical_category = (
                row.get("canonical_category") or osm_business_category(row["tags"] or {})
            )
            features.append(
                OsmViewportFeature(
                    id=f"{row['osm_type']}/{row['osm_id']}",
                    geometry=row["geometry"],
                    properties=OsmViewportProperties(
                        feature_id=f"{row['osm_type']}/{row['osm_id']}",
                        osm_type=row["osm_type"],
                        osm_id=row["osm_id"],
                        category=row["category"],
                        canonical_category=canonical_category,
                        name=(row["tags"] or {}).get("name"),
                        primary_type=row["primary_type"],
                        natural=(row["tags"] or {}).get("natural"),
                        feature_type="point" if row["dimension"] == 0 else "polygon",
                        canonical_floor=(
                            row.get("canonical_floor") or osm_floor_group(row["tags"] or {})
                        ),
                        mapped_area_m2=row.get("mapped_area_m2"),
                        occupancy_status=occupancy.status,
                        occupancy_source="OSM" if occupancy.status == "VACANT" else None,
                        stadtplaner=row.get("linked_polygons") or [],
                        external_links=external_links_from_osm_tags(row["tags"] or {}),
                    ),
                )
            )
        summary = dict(Counter(feature.properties.category for feature in features))
        canonical_summary = dict(Counter(
            feature.properties.canonical_category for feature in features
            if feature.properties.canonical_category
        ))
        business_count = sum(bool(feature.properties.canonical_category) for feature in features)
        dates = [row["imported_at"] for row in rows if row["imported_at"] is not None]
        return OsmViewportFeatureCollection(
            features=features,
            meta=OsmViewportMeta(
                count=len(features),
                truncated=truncated,
                zoom=query.zoom,
                summary=summary,
                canonical_summary=canonical_summary,
                canonical_facets=facet_counts or canonical_summary,
                business_count=business_count,
                context_count=len(features) - business_count,
                deduplicated_linked_count=linked_count,
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
    session: AsyncSession, query: OsmViewportQuery,
    filters: PolygonFilterParams | None = None,
) -> OsmViewportFeatureCollection:
    return OsmViewportFeatureCollection.model_validate_json(
        await viewport_features_json(session, query, filters)
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

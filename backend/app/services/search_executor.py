import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.search import (
    SearchIntent,
    SearchMapAction,
    SearchPlan,
    SearchResponse,
)
from app.services.analysis_area_api import (
    area_analytics,
    area_comparison,
    area_detail_by_slug,
    areas_geojson,
)
from app.services.osm_canonical import (
    osm_business_category_sql,
    osm_floor_group_sql,
    osm_status_sql,
)

SEARCH_RESULT_LIMIT = 200
_OSM_CATEGORY_SQL = osm_business_category_sql("osm.tags")
_OSM_STATUS_SQL = osm_status_sql("osm.tags")
_OSM_FLOOR_SQL = osm_floor_group_sql("osm.tags")

SEARCH_OSM_FEATURES_SQL = text(f"""
WITH target AS (
  SELECT geometry FROM analysis_areas WHERE uuid = CAST(:area_id AS uuid)
)
SELECT 'OSM' AS source, osm.osm_type || ':' || osm.osm_id::text AS id,
       coalesce(osm.tags->>'name', osm.tags->>'shop', osm.tags->>'amenity', 'OpenStreetMap-Objekt') AS name,
       {_OSM_CATEGORY_SQL} AS category, {_OSM_STATUS_SQL} AS occupancy_status,
       ST_AsGeoJSON(osm.geometry, 6)::json AS geometry
FROM osm_features osm CROSS JOIN target
WHERE osm.geometry && target.geometry
  AND ST_Covers(target.geometry, ST_PointOnSurface(osm.geometry))
  AND (cardinality(CAST(:categories AS text[])) = 0
       OR {_OSM_CATEGORY_SQL} = ANY(CAST(:categories AS text[])))
  AND (cardinality(CAST(:statuses AS text[])) = 0
       OR {_OSM_STATUS_SQL} = ANY(CAST(:statuses AS text[])))
  AND (cardinality(CAST(:osm_amenities AS text[])) = 0
       OR lower(osm.tags->>'amenity') = ANY(CAST(:osm_amenities AS text[])))
  AND (cardinality(CAST(:floors AS text[])) = 0
       OR {_OSM_FLOOR_SQL} = ANY(CAST(:floors AS text[])))
  AND cardinality(CAST(:area_sizes AS text[])) = 0
  AND cardinality(CAST(:business_structures AS text[])) = 0
  AND (:geometry_filter = 'ALL'
       OR (:geometry_filter = 'POLYGONS_ONLY' AND ST_Dimension(osm.geometry) = 2)
       OR (:geometry_filter = 'POINTS_ONLY' AND ST_Dimension(osm.geometry) = 0))
  AND (NOT :deduplicate_linked OR NOT EXISTS (
    SELECT 1 FROM polygon_osm_sources source
    WHERE source.osm_type = osm.osm_type AND source.osm_id = osm.osm_id
  ))
  AND ST_IsValid(osm.geometry)
ORDER BY (osm.tags ? 'name') DESC, osm.osm_type, osm.osm_id
LIMIT :limit
""")

SEARCH_POLYGON_FEATURES_SQL = text("""
SELECT 'STADTPLANNER' AS source, polygon.uuid::text AS id, polygon.name,
       polygon.category, polygon.occupancy_status,
       ST_AsGeoJSON(polygon.geometry, 6)::json AS geometry
FROM user_polygons polygon
JOIN polygon_analysis_areas assignment ON assignment.polygon_id = polygon.id
JOIN analysis_areas area ON area.id = assignment.analysis_area_id
WHERE area.uuid = CAST(:area_id AS uuid)
  AND (cardinality(CAST(:categories AS text[])) = 0
       OR polygon.category = ANY(CAST(:categories AS text[])))
  AND (cardinality(CAST(:statuses AS text[])) = 0
       OR polygon.occupancy_status = ANY(CAST(:statuses AS text[])))
  AND (cardinality(CAST(:floors AS text[])) = 0 OR CASE
       WHEN polygon.floor = 'UG' THEN 'UG'
       WHEN polygon.floor = 'EG' THEN 'EG'
       WHEN polygon.floor IN ('OG','1OG','2OG','3OG','DG') THEN 'OG'
       END = ANY(CAST(:floors AS text[])))
  AND (cardinality(CAST(:area_sizes AS text[])) = 0
       OR polygon.properties->>'size' = ANY(CAST(:area_sizes AS text[])))
  AND (cardinality(CAST(:business_structures AS text[])) = 0
       OR polygon.business_structure = ANY(CAST(:business_structures AS text[])))
  AND cardinality(CAST(:osm_amenities AS text[])) = 0
  AND :geometry_filter <> 'POINTS_ONLY'
ORDER BY polygon.updated_at DESC, polygon.id DESC
LIMIT :limit
""")

COUNT_FEATURES_SQL = text(f"""
WITH target AS (
  SELECT id, geometry FROM analysis_areas WHERE uuid = CAST(:area_id AS uuid)
), counts AS (
  SELECT 'OSM' AS source, count(*)::integer AS count
  FROM osm_features osm CROSS JOIN target
  WHERE :include_osm
    AND osm.geometry && target.geometry
    AND ST_Covers(target.geometry, ST_PointOnSurface(osm.geometry))
    AND (cardinality(CAST(:categories AS text[])) = 0
         OR {_OSM_CATEGORY_SQL} = ANY(CAST(:categories AS text[])))
    AND (cardinality(CAST(:statuses AS text[])) = 0
         OR {_OSM_STATUS_SQL} = ANY(CAST(:statuses AS text[])))
    AND (cardinality(CAST(:floors AS text[])) = 0
         OR {_OSM_FLOOR_SQL} = ANY(CAST(:floors AS text[])))
    AND cardinality(CAST(:area_sizes AS text[])) = 0
    AND cardinality(CAST(:business_structures AS text[])) = 0
    AND (:geometry_filter = 'ALL'
         OR (:geometry_filter = 'POLYGONS_ONLY' AND ST_Dimension(osm.geometry) = 2)
         OR (:geometry_filter = 'POINTS_ONLY' AND ST_Dimension(osm.geometry) = 0))
    AND (NOT :deduplicate_linked OR NOT EXISTS (
      SELECT 1 FROM polygon_osm_sources source
      WHERE source.osm_type = osm.osm_type AND source.osm_id = osm.osm_id
    ))
  UNION ALL
  SELECT 'STADTPLANNER', count(*)::integer
  FROM user_polygons polygon
  JOIN polygon_analysis_areas assignment ON assignment.polygon_id = polygon.id
  CROSS JOIN target
  WHERE :include_stadtplaner AND assignment.analysis_area_id = target.id
    AND (cardinality(CAST(:categories AS text[])) = 0
         OR polygon.category = ANY(CAST(:categories AS text[])))
    AND (cardinality(CAST(:statuses AS text[])) = 0
         OR polygon.occupancy_status = ANY(CAST(:statuses AS text[])))
    AND (cardinality(CAST(:floors AS text[])) = 0 OR CASE
         WHEN polygon.floor = 'UG' THEN 'UG'
         WHEN polygon.floor = 'EG' THEN 'EG'
         WHEN polygon.floor IN ('OG','1OG','2OG','3OG','DG') THEN 'OG'
         END = ANY(CAST(:floors AS text[])))
    AND (cardinality(CAST(:area_sizes AS text[])) = 0
         OR polygon.properties->>'size' = ANY(CAST(:area_sizes AS text[])))
    AND (cardinality(CAST(:business_structures AS text[])) = 0
         OR polygon.business_structure = ANY(CAST(:business_structures AS text[])))
    AND :geometry_filter <> 'POINTS_ONLY'
)
SELECT source, count FROM counts ORDER BY source
""")


async def execute_search(
    session: AsyncSession, query: str, plan: SearchPlan
) -> SearchResponse:
    if plan.intent == SearchIntent.CHANGE_FILTERS:
        return _response(query, plan, "Die Kartenfilter wurden aktualisiert.")

    if plan.intent == SearchIntent.SHOW_ANALYSIS_AREAS:
        collection = await areas_geojson(session)
        features = [
            feature for feature in collection.get("features", [])
            if feature.get("properties", {}).get("area_type") == plan.area_type
        ]
        data = {"type": "FeatureCollection", "features": features}
        label = {
            "MUNICIPALITY": "Gemeinden",
            "DISTRICT": "Stadtteile",
            "QUARTER": "Quartiere",
        }.get(str(plan.area_type), "Gebiete")
        return _response(query, plan, f"Ich zeige {len(features)} {label}.", data=data)

    area = plan.area
    if area is None:
        raise ValueError("Für diesen Suchplan fehlt ein aufgelöstes Gebiet.")
    detail = await area_detail_by_slug(session, area.slug)
    if detail is None:
        raise SearchExecutionError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
    bounds = tuple(detail.bbox)

    if plan.intent == SearchIntent.SHOW_AREA:
        area_size = f"{detail.area_m2 / 1_000_000:.2f} km²".replace(".", ",")
        answer = (
            f"{area.name} ist {area_size} groß."
            if "wie groß" in query.casefold() or "wie gross" in query.casefold()
            else f"Ich zeige {area.name}."
        )
        return _response(
            query, plan, answer,
            data=detail.model_dump(mode="json"), bounds=bounds,
        )
    if plan.intent == SearchIntent.SHOW_FEATURES:
        data = await _feature_collection(session, plan)
        return _response(
            query, plan, f"Ich zeige {len(data['features'])} passende Objekte in {area.name}.",
            data=data, bounds=bounds,
        )
    if plan.intent == SearchIntent.COUNT_FEATURES:
        counts = await _feature_counts(session, plan)
        total = sum(item["count"] for item in counts)
        return _response(
            query, plan, f"In {area.name} wurden {total} passende Objekte gefunden.",
            data={"count": total, "by_source": counts}, bounds=bounds,
        )

    common_filters = {
        "categories": tuple(plan.filters.categories),
        "floors": tuple(plan.filters.floors),
        "area_sizes": tuple(plan.filters.area_sizes),
        "occupancy_statuses": tuple(plan.filters.occupancy_statuses),
        "business_structures": tuple(plan.filters.business_structures),
        "sources": tuple(plan.filters.sources),
    }
    area_id = uuid.UUID(area.id)
    if plan.intent == SearchIntent.ASK_ANALYTICS:
        analytics = await area_analytics(session, area_id, **common_filters)
        if analytics is None:
            raise SearchExecutionError("AREA_NOT_FOUND", "Das Gebiet wurde nicht gefunden.", 404)
        return _response(
            query, plan, f"Hier sind die öffentlichen Kennzahlen für {area.name}.",
            data=analytics.model_dump(mode="json"), bounds=bounds,
        )
    if plan.intent == SearchIntent.COMPARE_AREA:
        comparison = await area_comparison(session, area_id, **common_filters)
        if comparison is None:
            raise SearchExecutionError(
                "COMPARISON_NOT_AVAILABLE",
                "Für dieses Gebiet ist kein Vergleich mit der Gesamtstadt verfügbar.",
                404,
            )
        return _response(
            query, plan, f"Ich vergleiche {area.name} mit der Gesamtstadt.",
            data=comparison.model_dump(mode="json"), bounds=bounds,
        )
    raise SearchExecutionError("UNSUPPORTED_SEARCH_INTENT", "Der Suchplan wird nicht unterstützt.")


class SearchExecutionError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _params(plan: SearchPlan) -> dict:
    return {
        "area_id": plan.area.id if plan.area else None,
        "categories": plan.filters.categories,
        "statuses": plan.filters.occupancy_statuses,
        "floors": plan.filters.floors,
        "area_sizes": plan.filters.area_sizes,
        "business_structures": plan.filters.business_structures,
        "geometry_filter": plan.geometry_filter.value,
        "osm_amenities": plan.osm_amenities,
    }


def _enabled_sources(plan: SearchPlan) -> set[str]:
    return set(plan.filters.sources or ("OSM", "STADTPLANNER"))


async def _feature_collection(session: AsyncSession, plan: SearchPlan) -> dict:
    params = _params(plan)
    sources = _enabled_sources(plan)
    rows: list[dict] = []
    remaining = SEARCH_RESULT_LIMIT
    if "STADTPLANNER" in sources:
        result = await session.execute(
            SEARCH_POLYGON_FEATURES_SQL, {**params, "limit": remaining}
        )
        rows.extend(dict(row) for row in result.mappings().all())
        remaining -= len(rows)
    if "OSM" in sources and remaining > 0:
        result = await session.execute(
            SEARCH_OSM_FEATURES_SQL,
            {**params, "limit": remaining, "deduplicate_linked": "STADTPLANNER" in sources},
        )
        rows.extend(dict(row) for row in result.mappings().all())
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": row["id"],
                "geometry": row["geometry"],
                "properties": {key: value for key, value in row.items() if key != "geometry"},
            }
            for row in rows[:SEARCH_RESULT_LIMIT]
        ],
        "meta": {"count": min(len(rows), SEARCH_RESULT_LIMIT), "limit": SEARCH_RESULT_LIMIT},
    }


async def _feature_counts(session: AsyncSession, plan: SearchPlan) -> list[dict]:
    sources = _enabled_sources(plan)
    result = await session.execute(
        COUNT_FEATURES_SQL,
        {
            **_params(plan),
            "include_osm": "OSM" in sources,
            "include_stadtplaner": "STADTPLANNER" in sources,
            "deduplicate_linked": "STADTPLANNER" in sources,
        },
    )
    return [
        {"source": str(row["source"]), "count": int(row["count"])}
        for row in result.mappings().all()
    ]


def _response(
    query: str,
    plan: SearchPlan,
    answer: str,
    *,
    data: object = None,
    bounds: tuple[float, float, float, float] | None = None,
) -> SearchResponse:
    return SearchResponse(
        query=query,
        plan=plan,
        answer=answer,
        map_action=SearchMapAction(
            type=plan.map_action.type,
            fit_bounds=plan.map_action.fit_bounds,
            bounds=bounds,
        ),
        data=data,
    )

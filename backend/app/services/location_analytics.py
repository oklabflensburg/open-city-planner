from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analytics import LocationAnalysis, NearestPoi, PoiCount
from app.services.poi_categories import POI_CATEGORY_LABELS, POI_CATEGORY_SQL

_BASE_CTE = f"""
WITH target AS (
  SELECT geometry FROM user_polygons WHERE slug = :slug
), candidates AS (
  SELECT osm.osm_type, osm.osm_id, osm.tags, osm.imported_at,
         ST_Distance(osm.geometry::geography, ST_PointOnSurface(target.geometry)::geography) AS distance_m,
         {POI_CATEGORY_SQL} AS category
  FROM osm_features osm CROSS JOIN target
  WHERE osm.geometry && ST_Expand(target.geometry, :radius_m / 50000.0)
    AND ST_DWithin(osm.geometry::geography, ST_PointOnSurface(target.geometry)::geography, :radius_m)
)
"""

POI_COUNTS_SQL = text(_BASE_CTE + """
SELECT category, count(*) AS count, max(imported_at) AS reference_date
FROM candidates WHERE category IS NOT NULL
GROUP BY category ORDER BY category
""")

NEAREST_TRANSIT_SQL = text(_BASE_CTE + """
SELECT category, tags->>'name' AS name, distance_m
FROM candidates WHERE category = 'public_transport'
ORDER BY distance_m ASC LIMIT 1
""")


async def polygon_location_analysis(
    session: AsyncSession, *, slug: str, radius_m: int
) -> LocationAnalysis | None:
    exists = await session.scalar(text("SELECT EXISTS(SELECT 1 FROM user_polygons WHERE slug = :slug)"), {"slug": slug})
    if not exists:
        return None
    params = {"slug": slug, "radius_m": radius_m}
    rows = (await session.execute(POI_COUNTS_SQL, params)).mappings().all()
    nearest_row = (await session.execute(NEAREST_TRANSIT_SQL, params)).mappings().first()
    reference_dates = [row["reference_date"] for row in rows if row["reference_date"] is not None]
    nearest = None
    if nearest_row:
        nearest = NearestPoi(
            category="public_transport",
            label=POI_CATEGORY_LABELS["public_transport"],
            name=nearest_row["name"],
            distance_m=round(float(nearest_row["distance_m"]), 1),
        )
    return LocationAnalysis(
        polygon_slug=slug,
        radius_m=radius_m,
        poi_counts=[
            PoiCount(category=row["category"], label=POI_CATEGORY_LABELS[row["category"]], count=int(row["count"]))
            for row in rows
        ],
        nearest_public_transport=nearest,
        reference_date=max(reference_dates) if reference_dates else None,
    )

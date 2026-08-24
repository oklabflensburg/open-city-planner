from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.polygon_directory import PolygonDirectoryItem, PolygonDirectoryPage

DIRECTORY_SQL = text("""
SELECT polygon.slug, polygon.name, polygon.category, polygon.floor,
       polygon.address_display_name, polygon.occupancy_status,
       polygon.business_structure, polygon.updated_at,
       district.slug AS district_slug, district.name AS district_name,
       quarter.slug AS quarter_slug, quarter.name AS quarter_name
FROM user_polygons polygon
LEFT JOIN LATERAL (
  SELECT area.slug, area.name
  FROM polygon_analysis_areas assignment
  JOIN analysis_areas area ON area.id = assignment.analysis_area_id
  WHERE assignment.polygon_id = polygon.id AND area.area_type = 'DISTRICT'
  ORDER BY assignment.overlap_ratio DESC NULLS LAST, area.name
  LIMIT 1
) district ON true
LEFT JOIN LATERAL (
  SELECT area.slug, area.name
  FROM polygon_analysis_areas assignment
  JOIN analysis_areas area ON area.id = assignment.analysis_area_id
  WHERE assignment.polygon_id = polygon.id AND area.area_type = 'QUARTER'
  ORDER BY assignment.overlap_ratio DESC NULLS LAST, area.name
  LIMIT 1
) quarter ON true
ORDER BY polygon.category, lower(polygon.name), polygon.slug
OFFSET :offset LIMIT :limit
""")


async def polygon_directory_page(
    session: AsyncSession, *, offset: int, limit: int
) -> PolygonDirectoryPage:
    total = int(
        (await session.execute(text("SELECT count(*) FROM user_polygons"))).scalar_one()
    )
    rows = (
        await session.execute(DIRECTORY_SQL, {"offset": offset, "limit": limit})
    ).mappings().all()
    items = [PolygonDirectoryItem(**dict(row)) for row in rows]
    consumed = offset + len(items)
    return PolygonDirectoryPage(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        next_offset=consumed if consumed < total else None,
    )

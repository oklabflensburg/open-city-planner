from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.polygon_directory import PolygonDirectoryItem, PolygonDirectoryPage

DIRECTORY_SQL = text("""
SELECT polygon.slug, polygon.name, polygon.category, polygon.floor,
       polygon.address_display_name, polygon.occupancy_status,
       polygon.business_structure, polygon.updated_at
FROM user_polygons polygon
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

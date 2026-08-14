from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key
from app.cache.service import cache_service
from app.core.config import get_settings
from app.schemas.analytics import ComparablePolygon, ComparableResult
from app.services.cache_versions import cache_version

COMPARABLES_SQL = text("""
WITH target AS (
  SELECT id, slug, category, floor, geometry,
         ST_Area(ST_Transform(geometry, 25832)) AS area_m2
  FROM user_polygons WHERE slug = :slug
), candidates AS (
  SELECT p.slug, p.name, p.category, p.floor,
         ST_Area(ST_Transform(p.geometry, 25832)) AS area_m2,
         ST_Distance(ST_PointOnSurface(p.geometry)::geography, ST_PointOnSurface(t.geometry)::geography) AS distance_m,
         (CASE WHEN p.category = t.category THEN 0.45 ELSE 0 END)
         + (CASE WHEN coalesce(p.floor, '') = coalesce(t.floor, '') THEN 0.15 ELSE 0 END)
         + 0.25 * GREATEST(0, 1 - abs(ST_Area(ST_Transform(p.geometry, 25832)) - t.area_m2) / GREATEST(t.area_m2, 1))
         + 0.15 * GREATEST(0, 1 - ST_Distance(ST_PointOnSurface(p.geometry)::geography, ST_PointOnSurface(t.geometry)::geography) / :max_distance_m)
         AS similarity_score
  FROM user_polygons p CROSS JOIN target t
  WHERE p.id <> t.id
    AND p.geometry && ST_Expand(t.geometry, :max_distance_m / 50000.0)
)
SELECT * FROM candidates
WHERE distance_m <= :max_distance_m
ORDER BY similarity_score DESC, distance_m ASC
LIMIT :limit
""")


async def _comparable_polygons_uncached(
    session: AsyncSession, *, slug: str, limit: int = 5, max_distance_m: int = 2000
) -> ComparableResult | None:
    exists = await session.scalar(text("SELECT EXISTS(SELECT 1 FROM user_polygons WHERE slug = :slug)"), {"slug": slug})
    if not exists:
        return None
    rows = (await session.execute(COMPARABLES_SQL, {"slug": slug, "limit": limit, "max_distance_m": max_distance_m})).mappings().all()
    return ComparableResult(
        polygon_slug=slug,
        items=[
            ComparablePolygon(
                slug=row["slug"], title=row["name"], distance_m=round(float(row["distance_m"]), 1),
                area_m2=round(float(row["area_m2"]), 1), category=row["category"], floor=row["floor"],
                similarity_score=round(float(row["similarity_score"]), 3),
            ) for row in rows
        ],
    )


async def comparable_polygons(
    session: AsyncSession, *, slug: str, limit: int = 5, max_distance_m: int = 2000
) -> ComparableResult | None:
    version = await cache_version(session, "polygons")
    key = build_cache_key(
        "polygons:comparables",
        {"slug": slug, "limit": limit, "max_distance_m": max_distance_m, "scope": "public"},
        version=version,
    )

    async def compute() -> dict | None:
        result = await _comparable_polygons_uncached(
            session, slug=slug, limit=limit, max_distance_m=max_distance_m
        )
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().comparable_cache_ttl,
        resource="polygon-comparables",
        compute=compute,
    )
    return ComparableResult.model_validate(data) if data else None

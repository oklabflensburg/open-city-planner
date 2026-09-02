from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cache_versions import bump_cache_versions

GIS_MUTATION_CACHE_NAMESPACES = ("polygons", "osm")


async def invalidate_gis_after_mutation(session: AsyncSession) -> None:
    """Version every server-side view that depends on polygon mutations.

    The version update participates in the mutation transaction. A successful
    response therefore cannot expose an old polygon overview
    or OSM viewport/deduplication snapshot under the current cache key.
    """
    await bump_cache_versions(session, GIS_MUTATION_CACHE_NAMESPACES)

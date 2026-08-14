import argparse
import asyncio

from app.db.session import AsyncSessionLocal
from app.services.cache_versions import bump_cache_versions

ALLOWED = {"osm", "analytics", "analysis-areas", "polygons"}


async def run(namespaces: tuple[str, ...]) -> None:
    invalid = set(namespaces) - ALLOWED
    if invalid:
        raise SystemExit(f"Ungültige Namespaces: {', '.join(sorted(invalid))}")
    async with AsyncSessionLocal() as session:
        await bump_cache_versions(session, namespaces)
        await session.commit()
    print("invalidated: " + ", ".join(namespaces))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Persistente Cache-Versionen erhöhen")
    parser.add_argument("namespaces", nargs="+", choices=sorted(ALLOWED))
    args = parser.parse_args()
    asyncio.run(run(tuple(args.namespaces)))

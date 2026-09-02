import argparse
import asyncio

from app.cache.redis import close_redis, initialize_redis
from app.cache.service import cache_service
from app.core.config import get_settings


async def run(resource: str) -> None:
    await initialize_redis()
    try:
        prefix = get_settings().cache_prefix.strip(":")
        pattern = f"{prefix}:v1:{resource}:*" if resource else f"{prefix}:v1:*"
        print(f"deleted: {await cache_service.delete_pattern(pattern)}")
    finally:
        await close_redis()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stadtplaner-Cache per SCAN leeren")
    parser.add_argument("--resource", default="", help="Optionaler Key-Namespace, z. B. osm:viewport")
    args = parser.parse_args()
    asyncio.run(run(args.resource))

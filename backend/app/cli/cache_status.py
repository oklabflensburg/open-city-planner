import asyncio

from app.cache.redis import close_redis, initialize_redis
from app.cache.service import cache_service


async def run() -> None:
    await initialize_redis()
    try:
        for key, value in (await cache_service.stats()).items():
            print(f"{key}: {value}")
    finally:
        await close_redis()


if __name__ == "__main__":
    asyncio.run(run())

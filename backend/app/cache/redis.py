import logging

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_client: Redis | None = None


def get_redis() -> Redis | None:
    return _client


async def initialize_redis() -> None:
    global _client
    settings = get_settings()
    if not settings.redis_enabled:
        logger.info("Redis cache disabled")
        return
    client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,
        socket_connect_timeout=settings.redis_connect_timeout,
        socket_timeout=settings.redis_socket_timeout,
        max_connections=settings.redis_max_connections,
        health_check_interval=30,
    )
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        logger.warning("Redis unavailable, database fallback remains active: %s", type(exc).__name__)
        if settings.redis_required:
            raise RuntimeError("Redis is required but unavailable") from exc
        return
    _client = client
    logger.info("Redis cache connected")


async def close_redis() -> None:
    global _client
    client, _client = _client, None
    if client is not None:
        await client.aclose()


async def redis_health() -> str:
    if not get_settings().redis_enabled:
        return "disabled"
    client = _client
    if client is None:
        return "degraded"
    try:
        return "ok" if await client.ping() else "degraded"
    except Exception:  # noqa: BLE001 - health must not affect readiness
        return "degraded"

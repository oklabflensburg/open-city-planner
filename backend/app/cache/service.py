import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from typing import Any, TypeVar

from app.cache.redis import get_redis
from app.core.config import get_settings
from app.observability.metrics import (
    REDIS_ERRORS,
    REDIS_HITS,
    REDIS_MISSES,
    observe_redis,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")
_last_cache_status: ContextVar[str | None] = ContextVar("last_cache_status", default=None)


def last_cache_status() -> str | None:
    return _last_cache_status.get()


class CacheService:
    def __init__(self) -> None:
        self._local_locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> bytes | None:
        client = get_redis()
        if client is None:
            return None
        started = time.perf_counter()
        try:
            value = await client.get(key)
            if value is None:
                REDIS_MISSES.inc()
            else:
                REDIS_HITS.inc()
            observe_redis("get", started, result="hit" if value is not None else "miss", payload=value)
            return value
        except Exception as exc:  # noqa: BLE001
            REDIS_ERRORS.labels("get").inc()
            observe_redis("get", started, result="error")
            logger.warning("cache_error operation=get error=%s", type(exc).__name__)
            return None

    async def set(self, key: str, value: bytes, ttl: int) -> bool:
        client = get_redis()
        if client is None:
            return False
        started = time.perf_counter()
        try:
            await client.set(key, value, ex=ttl)
            observe_redis("set", started, result="success", payload=value)
            return True
        except Exception as exc:  # noqa: BLE001
            REDIS_ERRORS.labels("set").inc()
            observe_redis("set", started, result="error")
            logger.warning("cache_error operation=set error=%s", type(exc).__name__)
            return False

    async def delete(self, *keys: str) -> int:
        client = get_redis()
        if client is None or not keys:
            return 0
        started = time.perf_counter()
        try:
            deleted = int(await client.delete(*keys))
            observe_redis("delete", started, result="success")
            return deleted
        except Exception as exc:  # noqa: BLE001
            REDIS_ERRORS.labels("delete").inc()
            observe_redis("delete", started, result="error")
            logger.warning("cache_error operation=delete error=%s", type(exc).__name__)
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        client = get_redis()
        if client is None:
            return 0
        deleted = 0
        try:
            batch: list[bytes] = []
            async for key in client.scan_iter(match=pattern, count=250):
                batch.append(key)
                if len(batch) >= 250:
                    deleted += int(await client.delete(*batch))
                    batch.clear()
            if batch:
                deleted += int(await client.delete(*batch))
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_error operation=scan-delete error=%s", type(exc).__name__)
        return deleted

    async def get_many(self, keys: Sequence[str]) -> list[bytes | None]:
        client = get_redis()
        if client is None or not keys:
            return [None] * len(keys)
        started = time.perf_counter()
        try:
            values = list(await client.mget(list(keys)))
            REDIS_HITS.inc(sum(value is not None for value in values))
            REDIS_MISSES.inc(sum(value is None for value in values))
            observe_redis("mget", started, result="success")
            return values
        except Exception as exc:  # noqa: BLE001
            REDIS_ERRORS.labels("mget").inc()
            observe_redis("mget", started, result="error")
            logger.warning("cache_error operation=mget error=%s", type(exc).__name__)
            return [None] * len(keys)

    async def stats(self) -> dict[str, Any]:
        client = get_redis()
        if client is None:
            return {"connected": False}
        try:
            memory, stats = await client.info("memory"), await client.info("stats")
            return {
                "connected": True,
                "used_memory_human": memory.get("used_memory_human"),
                "maxmemory_human": memory.get("maxmemory_human"),
                "keyspace_hits": stats.get("keyspace_hits", 0),
                "keyspace_misses": stats.get("keyspace_misses", 0),
                "keys": int(await client.dbsize()),
            }
        except Exception as exc:  # noqa: BLE001
            return {"connected": False, "error": type(exc).__name__}

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            logger.warning("cache_error operation=decode")
            await self.delete(key)
            return None

    async def set_json(self, key: str, value: Any, ttl: int) -> bool:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode()
        if len(raw) > get_settings().cache_payload_warning_bytes:
            logger.warning("cache_payload_large bytes=%d", len(raw))
        return await self.set(key, raw, ttl)

    async def get_or_compute(
        self,
        key: str,
        *,
        ttl: int,
        resource: str,
        compute: Callable[[], Awaitable[T]],
    ) -> tuple[T, str]:
        cached = await self.get_json(key)
        if cached is not None:
            logger.debug("cache_hit resource=%s", resource)
            _last_cache_status.set("HIT")
            return cached, "HIT"
        logger.debug("cache_miss resource=%s", resource)
        local_lock = self._local_locks.setdefault(key, asyncio.Lock())
        async with local_lock:
            cached = await self.get_json(key)
            if cached is not None:
                _last_cache_status.set("HIT")
                return cached, "HIT"
            client = get_redis()
            lock_key = f"lock:{key}"
            token = uuid.uuid4().hex.encode()
            acquired = False
            if client is not None:
                try:
                    acquired = bool(
                        await client.set(
                            lock_key,
                            token,
                            nx=True,
                            ex=get_settings().cache_lock_ttl_seconds,
                        )
                    )
                except Exception:  # noqa: BLE001
                    acquired = False
                if not acquired:
                    deadline = time.monotonic() + get_settings().cache_lock_ttl_seconds
                    while time.monotonic() < deadline:
                        await asyncio.sleep(0.1)
                        cached = await self.get_json(key)
                        if cached is not None:
                            _last_cache_status.set("HIT")
                            return cached, "HIT"
            started = time.perf_counter()
            value = await compute()
            await self.set_json(key, value, ttl)
            logger.info(
                "cache_fill resource=%s query_time_ms=%.2f",
                resource,
                (time.perf_counter() - started) * 1000,
            )
            if acquired and client is not None:
                try:
                    await client.eval(
                        "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
                        1,
                        lock_key,
                        token,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("cache_lock_release_error error=%s", type(exc).__name__)
            self._local_locks.pop(key, None)
            _last_cache_status.set("MISS")
            return value, "MISS"

    async def get_or_compute_bytes(
        self,
        key: str,
        *,
        ttl: int,
        resource: str,
        compute: Callable[[], Awaitable[bytes]],
    ) -> tuple[bytes, str]:
        cached = await self.get(key)
        if cached is not None:
            _last_cache_status.set("HIT")
            return cached, "HIT"
        local_lock = self._local_locks.setdefault(key, asyncio.Lock())
        async with local_lock:
            try:
                cached = await self.get(key)
                if cached is not None:
                    _last_cache_status.set("HIT")
                    return cached, "HIT"
                client = get_redis()
                lock_key = f"lock:{key}"
                token = uuid.uuid4().hex.encode()
                acquired = False
                if client is not None:
                    try:
                        acquired = bool(
                            await client.set(
                                lock_key,
                                token,
                                nx=True,
                                ex=get_settings().cache_lock_ttl_seconds,
                            )
                        )
                    except Exception:  # noqa: BLE001
                        acquired = False
                    if not acquired:
                        for _ in range(5):
                            await asyncio.sleep(0.05)
                            cached = await self.get(key)
                            if cached is not None:
                                _last_cache_status.set("HIT")
                                return cached, "HIT"
                started = time.perf_counter()
                value = await compute()
                await self.set(key, value, ttl)
                logger.info(
                    "cache_fill resource=%s query_time_ms=%.2f",
                    resource,
                    (time.perf_counter() - started) * 1000,
                )
                if acquired and client is not None:
                    try:
                        await client.eval(
                            "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
                            1,
                            lock_key,
                            token,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("cache_lock_release_error error=%s", type(exc).__name__)
                _last_cache_status.set("MISS")
                return value, "MISS"
            finally:
                self._local_locks.pop(key, None)


cache_service = CacheService()

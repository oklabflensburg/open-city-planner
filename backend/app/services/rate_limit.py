import asyncio
import hashlib
import ipaddress
import time
from collections import OrderedDict
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.cache.redis import get_redis
from app.core.config import get_settings

_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


@dataclass
class _MemoryWindow:
    count: int
    expires_at: float


_memory_windows: OrderedDict[str, _MemoryWindow] = OrderedDict()
_memory_lock = asyncio.Lock()


def client_ip(request: Request) -> str:
    """Honor forwarding only when the direct peer is explicitly trusted."""
    peer = request.client.host if request.client else "unknown"
    try:
        peer_address = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    trusted = []
    for value in get_settings().trusted_proxy_list:
        try:
            trusted.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    if not any(peer_address in network for network in trusted):
        return peer
    candidate = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer


def rate_limit_key(request: Request, scope: str, discriminator: str | None = None) -> str:
    identity = client_ip(request)
    if discriminator:
        identity = f"{identity}:{discriminator.strip().lower()}"
    return f"{scope}:{hashlib.sha256(identity.encode()).hexdigest()}"


def _rate_limit_error(code: str, message: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"error": {"code": code, "message": message}},
        headers={"Retry-After": str(max(1, retry_after))},
    )


async def _check_memory(key: str, window: int) -> tuple[int, int]:
    now = time.monotonic()
    async with _memory_lock:
        expired = [name for name, value in _memory_windows.items() if value.expires_at <= now]
        for name in expired:
            _memory_windows.pop(name, None)
        current = _memory_windows.get(key)
        if current is None:
            current = _MemoryWindow(count=0, expires_at=now + window)
            _memory_windows[key] = current
        current.count += 1
        _memory_windows.move_to_end(key)
        while len(_memory_windows) > get_settings().rate_limit_memory_max_keys:
            _memory_windows.popitem(last=False)
        return current.count, max(1, int(current.expires_at - now + 0.999))


async def _check_redis(key: str, window: int) -> tuple[int, int]:
    client = get_redis()
    if client is None:
        raise ConnectionError("Redis security rate limiter is unavailable")
    redis_key = f"{get_settings().cache_prefix}:rate-limit:{key}"
    result = await client.eval(_FIXED_WINDOW_SCRIPT, 1, redis_key, window)
    return int(result[0]), max(1, int(result[1]))


async def check_rate_limit(
    key: str,
    *,
    attempts: int | None = None,
    window_seconds: int | None = None,
    scope: str | None = None,
    code: str = "RATE_LIMITED",
    message: str = "Zu viele Versuche. Bitte später erneut versuchen.",
) -> None:
    settings = get_settings()
    limit = attempts if attempts is not None else settings.auth_rate_limit_attempts
    window = (
        window_seconds if window_seconds is not None else settings.auth_rate_limit_window_seconds
    )
    scoped_key = f"{scope}:{key}" if scope else key
    try:
        if settings.auth_rate_limit_backend == "redis":
            count, retry_after = await _check_redis(scoped_key, window)
        else:
            count, retry_after = await _check_memory(scoped_key, window)
    except Exception as exc:
        if settings.rate_limit_fail_closed or settings.production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "RATE_LIMIT_UNAVAILABLE",
                        "message": "Die Sicherheitsprüfung ist vorübergehend nicht verfügbar.",
                    }
                },
                headers={"Retry-After": "5"},
            ) from exc
        count, retry_after = await _check_memory(scoped_key, window)
    if count > limit:
        raise _rate_limit_error(code, message, retry_after)


def reset_memory_rate_limits() -> None:
    """Clear the bounded development/test fallback."""
    _memory_windows.clear()

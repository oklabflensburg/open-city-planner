from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.config import get_settings

_buckets: dict[str, deque[datetime]] = defaultdict(deque)


def check_rate_limit(
    key: str,
    *,
    attempts: int | None = None,
    window_seconds: int | None = None,
    code: str = "RATE_LIMITED",
    message: str = "Zu viele Versuche. Bitte später erneut versuchen.",
) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    limit = attempts if attempts is not None else settings.auth_rate_limit_attempts
    window = window_seconds if window_seconds is not None else settings.auth_rate_limit_window_seconds
    window_start = now - timedelta(seconds=window)
    bucket = _buckets[key]
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": code, "message": message}},
        )
    bucket.append(now)

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.core.config import get_settings

_buckets: dict[str, deque[datetime]] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=settings.auth_rate_limit_window_seconds)
    bucket = _buckets[key]
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= settings.auth_rate_limit_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "RATE_LIMITED", "message": "Zu viele Versuche. Bitte später erneut versuchen."}},
        )
    bucket.append(now)

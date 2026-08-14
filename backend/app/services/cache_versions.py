import time
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import get_redis

_local_versions: dict[str, tuple[float, int]] = {}


async def cache_version(session: AsyncSession, namespace: str) -> int:
    if get_redis() is None:
        return 1
    cached = _local_versions.get(namespace)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    value = await session.scalar(
        text("SELECT version FROM cache_versions WHERE namespace=:namespace"),
        {"namespace": namespace},
    )
    version = int(value or 1)
    _local_versions[namespace] = (time.monotonic() + 5, version)
    return version


async def bump_cache_versions(session: AsyncSession, namespaces: Iterable[str]) -> None:
    names = tuple(dict.fromkeys(namespaces))
    if not names:
        return
    if not hasattr(session, "execute"):
        return
    await session.execute(
        text("""
          INSERT INTO cache_versions (namespace,version,updated_at)
          SELECT unnest(CAST(:names AS text[])),2,now()
          ON CONFLICT (namespace) DO UPDATE
          SET version=cache_versions.version+1,updated_at=now()
        """),
        {"names": list(names)},
    )
    for name in names:
        _local_versions.pop(name, None)

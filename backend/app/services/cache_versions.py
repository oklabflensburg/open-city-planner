import time
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import get_redis

_local_versions: dict[str, tuple[float, int]] = {}
# Session-local marker; only values from this transaction bypass the process cache.
_PENDING_BUMPS_KEY = "cache_versions.pending_bumps"


def _has_pending_bump(session: AsyncSession, namespace: str) -> bool:
    info = session.info
    if not isinstance(info, dict):
        return False
    transaction = session.get_transaction()
    pending = info.get(_PENDING_BUMPS_KEY)
    return (
        transaction is not None
        and isinstance(pending, tuple)
        and len(pending) == 2
        and pending[0] is transaction
        and isinstance(pending[1], set)
        and namespace in pending[1]
    )


async def cache_version(session: AsyncSession, namespace: str) -> int:
    if get_redis() is None:
        return 1
    transaction_has_bump = _has_pending_bump(session, namespace)
    if not transaction_has_bump:
        cached = _local_versions.get(namespace)
        if cached and cached[0] > time.monotonic():
            return cached[1]
    value = await session.scalar(
        text("SELECT version FROM cache_versions WHERE namespace=:namespace"),
        {"namespace": namespace},
    )
    version = int(value or 1)
    if not transaction_has_bump:
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
    info = session.info
    transaction = session.get_transaction() if isinstance(info, dict) else None
    if transaction is not None:
        pending = info.get(_PENDING_BUMPS_KEY)
        resources = (
            pending[1]
            if isinstance(pending, tuple)
            and len(pending) == 2
            and pending[0] is transaction
            and isinstance(pending[1], set)
            else set()
        )
        resources.update(names)
        info[_PENDING_BUMPS_KEY] = (transaction, resources)
    for name in names:
        _local_versions.pop(name, None)

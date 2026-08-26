"""Fachneutraler Legacy-Job-Adapter für den Domain-Event-Outbox-Dispatcher."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.events.bus import InProcessEventBus
from app.platform.events.outbox import OutboxDispatcher

type SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def domain_event_outbox_handler(
    bus: InProcessEventBus,
    *,
    session_factory: SessionFactory,
    worker_id: str,
    limit: int,
) -> Callable[[], Awaitable[dict[str, int]]]:
    """Erzeuge den injizierten Handler, ohne Host-Settings oder globale DB-Imports."""

    async def handler() -> dict[str, int]:
        dispatcher = OutboxDispatcher(bus, worker_id=worker_id)
        async with session_factory() as session:
            return await dispatcher.run_once(session, limit=limit)

    return handler


__all__ = ["domain_event_outbox_handler"]

"""Legacy-Adapter vom Polygon-Service zum fachneutralen Host-Event-Publisher."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.events import HostEventBusAdapter, InProcessEventBus
from app.services.polygon_events import PolygonCreated, PolygonDeleted, PolygonUpdated

_publisher = HostEventBusAdapter(InProcessEventBus(), module_id="polygons")


async def enqueue_polygon_event(
    session: AsyncSession,
    event: PolygonCreated | PolygonUpdated | PolygonDeleted,
) -> None:
    """Outbox-Schreibzugriff ohne versteckten Commit in der Transaktion des Callers."""

    await _publisher.publish_after_commit(event, session=session)

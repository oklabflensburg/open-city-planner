"""Transactional publisher for the public OSM postprocessing event."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.events import HostEventBusAdapter, InProcessEventBus
from app.platform.modules.sdk import OsmPostprocessingCompleted

_publisher = HostEventBusAdapter(InProcessEventBus(), module_id="osm")


async def enqueue_osm_postprocessing_completed(
    session: AsyncSession, event: OsmPostprocessingCompleted
) -> None:
    """Add the event to the caller's transaction without committing it."""

    await _publisher.publish_after_commit(event, session=session)


__all__ = ["enqueue_osm_postprocessing_completed"]

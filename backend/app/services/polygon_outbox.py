import uuid
import logging
from typing import Any
from datetime import datetime, UTC, timedelta

from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.polygon_outbox import PolygonOutbox
from app.models.user_polygon import UserPolygon
from app.services.notification_policy import NotificationEventType, DomainEvent
from app.services.notifications import notify_users, publish_notifications, subscription_recipient_ids
from app.services.polygons import enrich_polygon_address
from app.services.social_publishing import cancel_pending_polygon_publications

logger = logging.getLogger(__name__)

async def enqueue_polygon_mutation_event(
    session: AsyncSession,
    polygon_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> PolygonOutbox:
    event = PolygonOutbox(
        polygon_id=polygon_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    return event

def _now() -> datetime:
    return datetime.now(UTC)

from app.services.polygons import generate_unique_polygon_slug, polygon_slug_source

async def _process_created_event(session: AsyncSession, event: PolygonOutbox) -> None:
    polygon = await session.scalar(select(UserPolygon).where(UserPolygon.uuid == event.polygon_id))
    if not polygon:
        return
    success = await enrich_polygon_address(session, polygon)
    if success:
        polygon.slug = await generate_unique_polygon_slug(session, polygon_slug_source(polygon))

async def _process_updated_event(session: AsyncSession, event: PolygonOutbox) -> None:
    polygon = await session.scalar(select(UserPolygon).where(UserPolygon.uuid == event.polygon_id))
    if not polygon:
        return
    payload = event.payload
    geometry_changed = payload.get("geometry_changed", False)
    if geometry_changed:
        await enrich_polygon_address(session, polygon)

    occupancy_status_changed = payload.get("occupancy_status_changed", False)
    actor_id_str = payload.get("actor_user_id")
    actor_user_id = uuid.UUID(actor_id_str) if actor_id_str else None

    notification_event_type = (
        NotificationEventType.GIS_AREA_STATUS_CHANGED
        if occupancy_status_changed
        else NotificationEventType.GIS_AREA_UPDATED
    )
    recipients = await subscription_recipient_ids(
        session, resource_type="POLYGON", resource_id=str(polygon.uuid), event_type=notification_event_type
    )
    if polygon.created_by_user_id:
        recipients.append(polygon.created_by_user_id)

    notifications = await notify_users(
        session,
        recipients,
        DomainEvent(
            event_type=notification_event_type,
            actor_user_id=actor_user_id,
            resource_type="POLYGON",
            resource_id=str(polygon.uuid),
            resource_slug=polygon.slug,
            resource_title=polygon.name,
        ),
    )
    publish_notifications(notifications)

async def _process_deleted_event(session: AsyncSession, event: PolygonOutbox) -> None:
    payload = event.payload
    polygon_id = event.polygon_id
    deleted_by_str = payload.get("deleted_by_user_id")
    deleted_by_user_id = uuid.UUID(deleted_by_str) if deleted_by_str else None
    
    recipients = await subscription_recipient_ids(
        session,
        resource_type="POLYGON",
        resource_id=str(polygon_id),
        event_type=NotificationEventType.GIS_AREA_DELETED,
    )
    created_by_str = payload.get("created_by_user_id")
    if created_by_str:
        recipients.append(uuid.UUID(created_by_str))

    notifications = await notify_users(
        session,
        recipients,
        DomainEvent(
            event_type=NotificationEventType.GIS_AREA_DELETED,
            actor_user_id=deleted_by_user_id,
            resource_type="POLYGON",
            resource_id=str(polygon_id),
            resource_slug=payload.get("slug"),
            resource_title=payload.get("name"),
        ),
    )
    await cancel_pending_polygon_publications(session, polygon_id)
    publish_notifications(notifications)

async def process_due_polygon_outbox(session: AsyncSession, *, limit: int = 50) -> dict[str, int]:
    stale = _now() - timedelta(minutes=10)
    
    # Recover stale
    await session.execute(
        update(PolygonOutbox)
        .where(PolygonOutbox.status == "PROCESSING", or_(PolygonOutbox.processing_started_at.is_(None), PolygonOutbox.processing_started_at < stale))
        .values(status="PENDING", processing_started_at=None)
    )
    await session.commit()
    
    result = await session.scalars(
        select(PolygonOutbox)
        .where(PolygonOutbox.status == "PENDING", PolygonOutbox.next_attempt_at <= _now())
        .order_by(PolygonOutbox.next_attempt_at, PolygonOutbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = result.all()
    if not events:
        return {"processed": 0, "failed": 0, "dead_letter": 0}

    stats = {"processed": 0, "failed": 0, "dead_letter": 0}
    
    for event in events:
        event.status = "PROCESSING"
        event.processing_started_at = _now()
        event.attempt_count += 1
        await session.commit()
        
        success = False
        try:
            if event.event_type == "CREATED":
                await _process_created_event(session, event)
            elif event.event_type == "UPDATED":
                await _process_updated_event(session, event)
            elif event.event_type == "DELETED":
                await _process_deleted_event(session, event)
            success = True
        except Exception as e:
            logger.exception("Polygon outbox event failed event_id=%s", event.id)
            event.last_error = str(e)
            
        if success:
            event.status = "COMPLETED"
            event.completed_at = _now()
            stats["processed"] += 1
        else:
            if event.attempt_count >= 8:
                event.status = "DEAD_LETTER"
                stats["dead_letter"] += 1
            else:
                event.status = "PENDING"
                event.next_attempt_at = _now() + timedelta(minutes=2 ** event.attempt_count)
                stats["failed"] += 1
                
        await session.commit()
        
    return stats

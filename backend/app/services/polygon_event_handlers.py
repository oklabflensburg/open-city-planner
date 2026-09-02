"""Explizite Legacy-Consumer-Adapter für den Polygon-Pilotflow aus #96."""

import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user_polygon import UserPolygon
from app.platform.events import HostEventBusAdapter, InProcessEventBus
from app.platform.modules.sdk import EventEnvelope
from app.services.notification_policy import DomainEvent, NotificationEventType
from app.services.notifications import (
    notify_users,
    publish_notifications,
    subscription_recipient_ids,
)
from app.services.polygons import (
    enrich_polygon_address,
    generate_unique_polygon_slug,
    polygon_slug_source,
)


def register_polygon_event_handlers(bus: InProcessEventBus) -> None:
    """Begrenzte Legacy-Subscriberregistrierung des Polygon-Pilotflows."""

    polygons = HostEventBusAdapter(bus, module_id="polygons")
    notifications = HostEventBusAdapter(bus, module_id="notifications")
    polygons.subscribe(
        "polygons.created",
        handler_id="polygons.enrich-created-address",
        versions=frozenset({1}),
        handler=_enrich_created_polygon,
    )
    polygons.subscribe(
        "polygons.updated",
        handler_id="polygons.enrich-updated-address",
        versions=frozenset({1}),
        handler=_enrich_updated_polygon,
    )
    notifications.subscribe(
        "polygons.updated",
        handler_id="notifications.polygon-updated",
        versions=frozenset({1}),
        handler=_notify_polygon_updated,
    )
    notifications.subscribe(
        "polygons.deleted",
        handler_id="notifications.polygon-deleted",
        versions=frozenset({1}),
        handler=_notify_polygon_deleted,
    )


async def _enrich_created_polygon(envelope: EventEnvelope) -> None:
    polygon_id = _uuid(envelope, "polygon_id")
    async with AsyncSessionLocal() as session:
        polygon = await session.scalar(select(UserPolygon).where(UserPolygon.uuid == polygon_id))
        if polygon is None:
            return
        if await enrich_polygon_address(session, polygon):
            polygon.slug = await generate_unique_polygon_slug(session, polygon_slug_source(polygon))
        await session.commit()


async def _enrich_updated_polygon(envelope: EventEnvelope) -> None:
    if not _boolean(envelope, "geometry_changed"):
        return
    polygon_id = _uuid(envelope, "polygon_id")
    async with AsyncSessionLocal() as session:
        polygon = await session.scalar(select(UserPolygon).where(UserPolygon.uuid == polygon_id))
        if polygon is None:
            return
        await enrich_polygon_address(session, polygon)
        await session.commit()


async def _notify_polygon_updated(envelope: EventEnvelope) -> None:
    polygon_id = _uuid(envelope, "polygon_id")
    actor_user_id = _optional_uuid(envelope, "actor_user_id")
    event_type = (
        NotificationEventType.GIS_AREA_STATUS_CHANGED
        if _boolean(envelope, "occupancy_status_changed")
        else NotificationEventType.GIS_AREA_UPDATED
    )
    async with AsyncSessionLocal() as session:
        polygon = await session.scalar(select(UserPolygon).where(UserPolygon.uuid == polygon_id))
        if polygon is None:
            return
        recipients = await subscription_recipient_ids(
            session,
            resource_type="POLYGON",
            resource_id=str(polygon.uuid),
            event_type=event_type,
        )
        if polygon.created_by_user_id:
            recipients.append(polygon.created_by_user_id)
        notifications = await notify_users(
            session,
            recipients,
            DomainEvent(
                event_type=event_type,
                actor_user_id=actor_user_id,
                resource_type="POLYGON",
                resource_id=str(polygon.uuid),
                resource_slug=polygon.slug,
                resource_title=polygon.name,
                metadata={"domain_event_id": str(envelope.event_id)},
            ),
        )
        await session.commit()
        publish_notifications(notifications)


async def _notify_polygon_deleted(envelope: EventEnvelope) -> None:
    polygon_id = _uuid(envelope, "polygon_id")
    event_type = NotificationEventType.GIS_AREA_DELETED
    async with AsyncSessionLocal() as session:
        recipients = await subscription_recipient_ids(
            session,
            resource_type="POLYGON",
            resource_id=str(polygon_id),
            event_type=event_type,
        )
        created_by_user_id = _optional_uuid(envelope, "created_by_user_id")
        if created_by_user_id:
            recipients.append(created_by_user_id)
        notifications = await notify_users(
            session,
            recipients,
            DomainEvent(
                event_type=event_type,
                actor_user_id=_uuid(envelope, "deleted_by_user_id"),
                resource_type="POLYGON",
                resource_id=str(polygon_id),
                resource_slug=_optional_string(envelope, "slug"),
                resource_title=_string(envelope, "name"),
                metadata={"domain_event_id": str(envelope.event_id)},
            ),
        )
        await session.commit()
        publish_notifications(notifications)


def _uuid(envelope: EventEnvelope, key: str) -> uuid.UUID:
    value = _string(envelope, key)
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f'Event field "{key}" must contain a UUID.') from exc


def _optional_uuid(envelope: EventEnvelope, key: str) -> uuid.UUID | None:
    value = envelope.payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f'Event field "{key}" must contain a UUID or null.')
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f'Event field "{key}" must contain a UUID or null.') from exc


def _string(envelope: EventEnvelope, key: str) -> str:
    value = envelope.payload.get(key)
    if not isinstance(value, str):
        raise TypeError(f'Event field "{key}" must contain a string.')
    return value


def _optional_string(envelope: EventEnvelope, key: str) -> str | None:
    value = envelope.payload.get(key)
    if value is not None and not isinstance(value, str):
        raise TypeError(f'Event field "{key}" must contain a string or null.')
    return value


def _boolean(envelope: EventEnvelope, key: str) -> bool:
    value = envelope.payload.get(key)
    if not isinstance(value, bool):
        raise TypeError(f'Event field "{key}" must contain a boolean.')
    return value

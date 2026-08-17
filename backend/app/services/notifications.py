import asyncio
import json
import logging
import math
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationPreference, NotificationSubscription
from app.models.user import User
from app.schemas.notification import (
    NotificationPage,
    NotificationPreferencesUpdate,
    NotificationRead,
)
from app.services.notification_policy import DomainEvent, NotificationEventType, notification_policy

logger = logging.getLogger(__name__)
DEDUPE_WINDOW = timedelta(minutes=5)
SECURITY_CATEGORIES = {"ACCOUNT"}


class NotificationBroker:
    """Process-local SSE fan-out; persistence remains the delivery source of truth."""

    def __init__(self) -> None:
        self._subscribers: dict[uuid.UUID, set[asyncio.Queue[NotificationRead]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, user_id: uuid.UUID) -> AsyncIterator[asyncio.Queue[NotificationRead]]:
        queue: asyncio.Queue[NotificationRead] = asyncio.Queue(maxsize=100)
        self._subscribers[user_id].add(queue)
        logger.info(
            "notification subscriber connected",
            extra={"notification_subscribers": self.subscriber_count},
        )
        try:
            yield queue
        finally:
            self._subscribers[user_id].discard(queue)
            if not self._subscribers[user_id]:
                self._subscribers.pop(user_id, None)
            logger.info(
                "notification subscriber disconnected",
                extra={"notification_subscribers": self.subscriber_count},
            )

    @property
    def subscriber_count(self) -> int:
        return sum(len(queues) for queues in self._subscribers.values())

    def publish(self, recipient_user_id: uuid.UUID, notification: NotificationRead) -> None:
        for queue in tuple(self._subscribers.get(recipient_user_id, ())):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(notification)

    @staticmethod
    def event_payload(notification: NotificationRead) -> str:
        return f"event: notification.created\ndata: {json.dumps(notification.model_dump(mode='json'), ensure_ascii=False)}\n\n"


notification_broker = NotificationBroker()


def notification_read(item: Notification) -> NotificationRead:
    return NotificationRead.model_validate(item)


async def get_preferences(session: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    preferences = await session.get(NotificationPreference, user_id)
    if preferences is None:
        preferences = NotificationPreference(user_id=user_id)
        session.add(preferences)
        await session.flush()
    return preferences


def _category_enabled(preferences: NotificationPreference, category: str) -> bool:
    if category in SECURITY_CATEGORIES:
        return True
    if not preferences.in_app_enabled:
        return False
    return {
        "GIS": preferences.notify_gis,
        "OSM": preferences.notify_osm,
        "DATA": preferences.notify_area_updates,
        "SOCIAL": preferences.notify_social,
        "SYSTEM": preferences.notify_system,
        "ADMIN": preferences.notify_system,
    }.get(category, True)


async def create_notification(
    session: AsyncSession,
    *,
    recipient_user_id: uuid.UUID,
    event: DomainEvent,
    allow_self: bool = False,
    dedupe_window: timedelta = DEDUPE_WINDOW,
) -> Notification | None:
    if event.actor_user_id == recipient_user_id and not allow_self:
        return None
    spec = notification_policy.render(event)
    preferences = await get_preferences(session, recipient_user_id)
    if not _category_enabled(preferences, spec.category):
        return None

    resource_key = event.resource_id or event.resource_slug or "global"
    dedupe_key = f"{event.event_type}:{resource_key}:{recipient_user_id}:{spec.dedupe_scope}"
    cutoff = datetime.now(UTC) - dedupe_window
    existing = await session.scalar(
        select(Notification)
        .where(
            Notification.recipient_user_id == recipient_user_id,
            Notification.dedupe_key == dedupe_key,
            Notification.created_at >= cutoff,
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    now = datetime.now(UTC)
    if existing is not None:
        occurrence_count = int((existing.event_metadata or {}).get("occurrence_count", 1)) + 1
        existing.title = spec.title
        existing.message = spec.message
        existing.priority = spec.priority
        existing.action_url = spec.action_url
        existing.action_label = spec.action_label
        existing.created_at = now
        existing.is_read = False
        existing.read_at = None
        existing.event_metadata = {**(event.metadata or {}), "occurrence_count": occurrence_count}
        await session.flush()
        return existing

    item = Notification(
        recipient_user_id=recipient_user_id,
        actor_user_id=event.actor_user_id,
        actor_type="USER" if event.actor_user_id else "SYSTEM",
        event_type=event.event_type.value,
        category=spec.category,
        priority=spec.priority,
        title=spec.title,
        message=spec.message,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        resource_slug=event.resource_slug,
        action_url=spec.action_url,
        action_label=spec.action_label,
        dedupe_key=dedupe_key,
        event_metadata=dict(event.metadata or {}),
    )
    session.add(item)
    await session.flush()
    return item


async def notify_users(
    session: AsyncSession,
    recipients: Iterable[uuid.UUID],
    event: DomainEvent,
    *,
    allow_self: bool = False,
) -> list[Notification]:
    created: list[Notification] = []
    for recipient in dict.fromkeys(recipients):
        item = await create_notification(
            session, recipient_user_id=recipient, event=event, allow_self=allow_self
        )
        if item is not None:
            created.append(item)
    if created:
        logger.info(
            "notifications created",
            extra={
                "notification_event_type": event.event_type.value,
                "notification_count": len(created),
            },
        )
    return created


async def notify_superusers(session: AsyncSession, event: DomainEvent) -> list[Notification]:
    recipients = await session.scalars(
        select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
    )
    return await notify_users(session, recipients.all(), event)


async def subscription_recipient_ids(
    session: AsyncSession,
    *,
    resource_type: str,
    resource_id: str,
    event_type: NotificationEventType,
) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(NotificationSubscription).where(
            NotificationSubscription.resource_type == resource_type,
            NotificationSubscription.resource_id == resource_id,
        )
    )
    return [
        row.user_id for row in rows if not row.event_types or event_type.value in row.event_types
    ]


def publish_notifications(items: Iterable[Notification]) -> None:
    delivered = 0
    for item in items:
        notification_broker.publish(item.recipient_user_id, notification_read(item))
        delivered += 1
    if delivered:
        logger.info("notifications delivered", extra={"notification_delivery_count": delivered})


async def list_notifications(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 30,
    category: str | None = None,
    unread_only: bool = False,
) -> NotificationPage:
    filters = [Notification.recipient_user_id == user_id]
    if category:
        filters.append(Notification.category == category)
    if unread_only:
        filters.append(Notification.is_read.is_(False))
    filters.append(
        or_(Notification.expires_at.is_(None), Notification.expires_at > datetime.now(UTC))
    )
    total = int(await session.scalar(select(func.count(Notification.id)).where(*filters)) or 0)
    unread = await unread_count(session, user_id)
    rows = await session.scalars(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return NotificationPage(
        items=[notification_read(item) for item in rows],
        total=total,
        unread_count=unread,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_user_id == user_id,
                Notification.is_read.is_(False),
                or_(Notification.expires_at.is_(None), Notification.expires_at > datetime.now(UTC)),
            )
        )
        or 0
    )


async def mark_read(session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    item = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user_id,
        )
    )
    if item is None:
        return False
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(UTC)
        await session.commit()
    return True


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await session.commit()
    return int(result.rowcount or 0)


async def update_preferences(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: NotificationPreferencesUpdate,
) -> NotificationPreference:
    preferences = await get_preferences(session, user_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(preferences, key, value)
    await session.commit()
    await session.refresh(preferences)
    return preferences


async def upsert_subscription(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    event_types: list[str],
) -> NotificationSubscription:
    item = await session.scalar(
        select(NotificationSubscription).where(
            NotificationSubscription.user_id == user_id,
            NotificationSubscription.resource_type == resource_type,
            NotificationSubscription.resource_id == resource_id,
        )
    )
    if item is None:
        item = NotificationSubscription(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_types=sorted(set(event_types)),
        )
        session.add(item)
    else:
        item.event_types = sorted(set(event_types))
    await session.commit()
    await session.refresh(item)
    return item


async def remove_subscription(
    session: AsyncSession, *, user_id: uuid.UUID, resource_type: str, resource_id: str
) -> bool:
    item = await session.scalar(
        select(NotificationSubscription).where(
            NotificationSubscription.user_id == user_id,
            NotificationSubscription.resource_type == resource_type,
            NotificationSubscription.resource_id == resource_id,
        )
    )
    if item is None:
        return False
    await session.delete(item)
    await session.commit()
    return True


async def cleanup_notifications(session: AsyncSession, *, retention_days: int) -> int:
    """Delete expired and old non-actionable notifications in a background job."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=max(1, retention_days))
    result = await session.execute(
        delete(Notification).where(
            or_(
                Notification.expires_at <= now,
                (
                    (Notification.created_at < cutoff)
                    & or_(
                        Notification.priority != "ACTION_REQUIRED", Notification.is_read.is_(True)
                    )
                ),
            )
        )
    )
    await session.commit()
    deleted = int(result.rowcount or 0)
    logger.info("notification cleanup complete", extra={"notifications_deleted": deleted})
    return deleted

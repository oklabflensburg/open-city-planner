import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification, NotificationPreference
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.services.notification_policy import DomainEvent, NotificationEventType, notification_policy
from app.services.notifications import (
    cleanup_notifications,
    create_notification,
    notification_broker,
    should_deliver_email,
    should_deliver_in_app,
    subscription_recipient_ids,
)


class NotificationSession:
    def __init__(self) -> None:
        self.preferences = NotificationPreference(
            user_id=uuid.uuid4(),
            in_app_enabled=True,
            notify_gis=True,
            notify_osm=True,
            notify_area_updates=True,
            notify_system=True,
        )
        self.notification: Notification | None = None
        self.added: list[object] = []
        self.user = User(
            id=self.preferences.user_id,
            email="notify@example.org",
            is_active=True,
            is_verified=True,
        )

    async def get(self, model: object, _key: object):
        if model is NotificationPreference:
            return self.preferences
        if model is User:
            return self.user
        return None

    async def scalar(self, _statement: object):
        return self.notification

    def add(self, item: object) -> None:
        self.added.append(item)
        if isinstance(item, Notification):
            item.id = uuid.uuid4()
            item.created_at = datetime.now(UTC)
            self.notification = item

    async def flush(self) -> None:
        pass


def polygon_event(actor_id: uuid.UUID) -> DomainEvent:
    return DomainEvent(
        event_type=NotificationEventType.GIS_AREA_UPDATED,
        actor_user_id=actor_id,
        resource_type="POLYGON",
        resource_id="polygon-1",
        resource_slug="testflaeche",
        resource_title="Testfläche",
    )


def email_eligible_event(actor_id: uuid.UUID) -> DomainEvent:
    return DomainEvent(
        event_type=NotificationEventType.GIS_AREA_STATUS_CHANGED,
        actor_user_id=actor_id,
        resource_type="POLYGON",
        resource_id="polygon-1",
        resource_slug="testflaeche",
        resource_title="Testfläche",
    )


def test_policy_uses_safe_known_routes_and_neutral_content() -> None:
    spec = notification_policy.render(polygon_event(uuid.uuid4()))
    assert spec.category == "GIS"
    assert spec.action_url == "/flaechen/testflaeche"
    assert "owner" not in spec.message.lower()
    assert "email" not in spec.message.lower()


@pytest.mark.parametrize("event_type", list(NotificationEventType))
def test_every_registered_event_has_controlled_copy_and_internal_action(event_type) -> None:
    spec = notification_policy.render(
        DomainEvent(
            event_type=event_type,
            resource_title="Öffentliche Testfläche",
            resource_slug="testflaeche",
            metadata={"email": "private@example.org", "internal_notes": "secret"},
        )
    )
    assert spec.title and spec.message
    assert spec.action_url is None or spec.action_url.startswith("/")
    assert "private@example.org" not in f"{spec.title} {spec.message}"
    assert "secret" not in f"{spec.title} {spec.message}"


@pytest.mark.asyncio
async def test_self_action_does_not_create_persistent_autosave_spam() -> None:
    user_id = uuid.uuid4()
    session = NotificationSession()
    result = await create_notification(
        session, recipient_user_id=user_id, event=polygon_event(user_id)
    )
    assert result is None
    assert session.notification is None


@pytest.mark.asyncio
async def test_five_updates_coalesce_to_one_unread_notification() -> None:
    recipient = uuid.uuid4()
    session = NotificationSession()
    for _ in range(5):
        result = await create_notification(
            session, recipient_user_id=recipient, event=polygon_event(uuid.uuid4())
        )
        assert result is session.notification
    assert len([item for item in session.added if isinstance(item, Notification)]) == 1
    assert session.notification is not None
    assert session.notification.event_metadata["occurrence_count"] == 5
    assert session.notification.is_read is False


@pytest.mark.asyncio
async def test_other_user_gets_exactly_one_notification_while_actor_is_suppressed() -> None:
    actor = uuid.uuid4()
    recipient = uuid.uuid4()
    session = NotificationSession()
    own = await create_notification(session, recipient_user_id=actor, event=polygon_event(actor))
    other = await create_notification(
        session, recipient_user_id=recipient, event=polygon_event(actor)
    )
    assert own is None
    assert other is not None
    assert len([item for item in session.added if isinstance(item, Notification)]) == 1


@pytest.mark.asyncio
async def test_email_only_notification_is_queued_without_in_app_visibility() -> None:
    session = NotificationSession()
    session.preferences.in_app_enabled = False
    session.preferences.email_enabled = True
    session.preferences.email_notify_gis = True

    item = await create_notification(
        session,
        recipient_user_id=session.preferences.user_id,
        event=email_eligible_event(uuid.uuid4()),
    )

    assert item is not None and item.in_app_visible is False
    assert len([value for value in session.added if isinstance(value, EmailOutbox)]) == 1


@pytest.mark.asyncio
async def test_in_app_only_notification_creates_no_email_delivery() -> None:
    session = NotificationSession()
    session.preferences.email_enabled = False

    item = await create_notification(
        session,
        recipient_user_id=session.preferences.user_id,
        event=email_eligible_event(uuid.uuid4()),
    )

    assert item is not None and item.in_app_visible is True
    assert not any(isinstance(value, EmailOutbox) for value in session.added)


def test_email_category_and_global_switch_are_independent_from_in_app() -> None:
    preferences = NotificationPreference(
        user_id=uuid.uuid4(),
        in_app_enabled=False,
        notify_gis=False,
        email_enabled=True,
        email_notify_gis=True,
    )
    assert should_deliver_in_app(preferences, "GIS") is False
    assert should_deliver_email(preferences, "GIS", email_eligible=True) is True
    preferences.email_notify_gis = False
    assert should_deliver_email(preferences, "GIS", email_eligible=True) is False
    assert should_deliver_email(preferences, "ACCOUNT", email_eligible=True) is False


@pytest.mark.asyncio
async def test_follow_policy_returns_only_matching_subscribers() -> None:
    matching = uuid.uuid4()
    wrong_event = uuid.uuid4()

    class SubscriptionRows:
        def all(self):
            return []

        def __iter__(self):
            return iter(
                [
                    type("Subscription", (), {"user_id": matching, "event_types": []})(),
                    type(
                        "Subscription",
                        (),
                        {"user_id": wrong_event, "event_types": ["GIS_AREA_DELETED"]},
                    )(),
                ]
            )

    class SubscriptionSession:
        async def scalars(self, _statement):
            return SubscriptionRows()

    recipients = await subscription_recipient_ids(
        SubscriptionSession(),
        resource_type="POLYGON",
        resource_id="polygon-1",
        event_type=NotificationEventType.GIS_AREA_UPDATED,
    )
    assert recipients == [matching]


@pytest.mark.asyncio
async def test_realtime_broker_delivers_only_to_the_subscribed_recipient() -> None:
    recipient = uuid.uuid4()
    other = uuid.uuid4()
    item = NotificationRead(
        id=uuid.uuid4(),
        event_type="IMPORT_COMPLETED",
        category="SYSTEM",
        priority="SUCCESS",
        title="Import abgeschlossen",
        message="Fertig",
        is_read=False,
        created_at=datetime.now(UTC),
        metadata={},
    )
    async with (
        notification_broker.subscribe(recipient) as own_queue,
        notification_broker.subscribe(other) as other_queue,
    ):
        notification_broker.publish(recipient, item)
        assert await asyncio.wait_for(own_queue.get(), timeout=0.1) == item
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(other_queue.get(), timeout=0.01)


def test_notification_model_has_recipient_unread_and_dedupe_indexes() -> None:
    indexes = {index.name for index in Notification.__table__.indexes}
    assert "idx_notifications_recipient_unread_created" in indexes
    assert "idx_notifications_dedupe" in indexes


@pytest.mark.asyncio
async def test_retention_cleanup_commits_background_delete() -> None:
    class Result:
        rowcount = 4

    class CleanupSession:
        committed = False
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Result()

        async def commit(self):
            self.committed = True

    session = CleanupSession()
    assert await cleanup_notifications(session, retention_days=90) == 4
    assert session.committed is True
    assert "DELETE FROM notifications" in str(session.statement)

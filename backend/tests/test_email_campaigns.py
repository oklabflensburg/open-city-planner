import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.email_campaign import EmailCampaign, EmailCampaignDelivery
from app.models.email_outbox import EmailOutbox
from app.models.email_unsubscribe import EmailUnsubscribeToken
from app.models.notification import NotificationPreference
from app.models.user import User
from app.services.admin_email_campaigns import CampaignConflict, start_campaign
from app.services.email_unsubscribe import unsubscribe_newsletter


def campaign(kind: str = "NEWSLETTER") -> EmailCampaign:
    return EmailCampaign(
        id=uuid.uuid4(),
        internal_name="September 2026",
        subject="Wichtige Änderung",
        title="Änderungen",
        content_html="<p>Inhalt</p>",
        content_text="Inhalt",
        campaign_type=kind,
        status="DRAFT",
        recipient_scope="VERIFIED_USERS",
        recipient_count=0,
        sent_count=0,
        failed_count=0,
        skipped_count=0,
        version=1,
    )


class CampaignSession:
    def __init__(self, item: EmailCampaign, users: list[User], opted_in: set[uuid.UUID]):
        self.campaign = item
        self.users = users
        self.opted_in = opted_in
        self.added: list[object] = []

    async def scalar(self, _statement):
        return self.campaign

    async def scalars(self, statement):
        return self.opted_in if "notification_preferences" in str(statement) else self.users

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        for item in self.added:
            if isinstance(item, EmailCampaignDelivery) and item.id is None:
                item.id = uuid.uuid4()

    async def commit(self) -> None:
        pass

    async def refresh(self, _item: object) -> None:
        pass


def recipient() -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.org",
        display_name="Max Mustermann",
        is_active=True,
        is_verified=True,
        email_pending=False,
    )


@pytest.mark.asyncio
async def test_newsletter_opt_out_creates_no_delivery() -> None:
    item = campaign()
    user = recipient()
    session = CampaignSession(item, [user], set())

    result = await start_campaign(session, item.id, recipient(), legal_confirmed=False)

    assert result.status == "COMPLETED"
    assert not any(isinstance(value, EmailCampaignDelivery) for value in session.added)
    assert not any(isinstance(value, EmailOutbox) for value in session.added)


@pytest.mark.asyncio
async def test_newsletter_opt_in_snapshots_one_idempotent_delivery() -> None:
    item = campaign()
    user = recipient()
    session = CampaignSession(item, [user], {user.id})

    await start_campaign(session, item.id, recipient(), legal_confirmed=False)
    await start_campaign(session, item.id, recipient(), legal_confirmed=False)

    deliveries = [value for value in session.added if isinstance(value, EmailCampaignDelivery)]
    outbox = [value for value in session.added if isinstance(value, EmailOutbox)]
    assert len(deliveries) == len(outbox) == 1
    assert outbox[0].idempotency_key == f"campaign:{item.id}:{user.id}"


@pytest.mark.asyncio
async def test_scheduled_campaign_stays_idempotent_until_due() -> None:
    item = campaign("SERVICE")
    item.scheduled_at = datetime.now(UTC) + timedelta(hours=1)
    user = recipient()
    session = CampaignSession(item, [user], set())

    await start_campaign(session, item.id, recipient(), legal_confirmed=False)
    await start_campaign(session, item.id, recipient(), legal_confirmed=False)

    assert item.status == "SCHEDULED"
    assert item.started_at is None
    assert len([value for value in session.added if isinstance(value, EmailOutbox)]) == 1


@pytest.mark.asyncio
async def test_legal_campaign_requires_confirmation_and_ignores_newsletter_opt_out() -> None:
    item = campaign("LEGAL")
    user = recipient()
    session = CampaignSession(item, [user], set())

    with pytest.raises(CampaignConflict):
        await start_campaign(session, item.id, recipient(), legal_confirmed=False)
    await start_campaign(session, item.id, recipient(), legal_confirmed=True)

    assert len([value for value in session.added if isinstance(value, EmailOutbox)]) == 1


@pytest.mark.asyncio
async def test_newsletter_unsubscribe_is_idempotent_and_disables_only_newsletter() -> None:
    user_id = uuid.uuid4()
    token = EmailUnsubscribeToken(
        id=uuid.uuid4(), token_hash="hash", user_id=user_id, scope="newsletter"
    )
    preferences = NotificationPreference(
        user_id=user_id,
        newsletter_enabled=True,
        email_enabled=True,
        email_notify_gis=True,
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = token
    session.get.return_value = preferences

    assert await unsubscribe_newsletter(session, "opaque-token-value-123456") is True
    assert await unsubscribe_newsletter(session, "opaque-token-value-123456") is True
    assert preferences.newsletter_enabled is False
    assert preferences.email_enabled is True
    assert preferences.email_notify_gis is True
    assert token.used_at is not None


def test_campaign_and_delivery_statuses_are_database_constrained() -> None:
    campaign_constraints = {item.name for item in EmailCampaign.__table__.constraints}
    delivery_constraints = {item.name for item in EmailCampaignDelivery.__table__.constraints}
    assert "ck_email_campaign_status" in campaign_constraints
    assert "ck_email_campaign_delivery_status" in delivery_constraints

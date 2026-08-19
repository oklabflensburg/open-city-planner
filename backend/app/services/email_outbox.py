import logging
import smtplib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.email_campaign import EmailCampaign, EmailCampaignDelivery
from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification
from app.models.user import User
from app.services.email_service import (
    EmailTemplateContent,
    EmailTemplateValidationError,
    display_name,
    get_template_content,
    render_email_template,
    send_rendered_email,
    send_welcome_email,
)
from app.services.email_unsubscribe import create_unsubscribe_token

logger = logging.getLogger(__name__)
RETRY_DELAYS = (60, 300, 1_800, 7_200, 21_600, 86_400)


def utcnow() -> datetime:
    return datetime.now(UTC)


def enqueue_welcome_email(session: AsyncSession, user: User) -> EmailOutbox | None:
    if not user.is_verified or user.welcome_email_sent_at is not None:
        return None
    event = EmailOutbox(
        template_key="welcome",
        delivery_type="WELCOME",
        idempotency_key=f"welcome:{user.id}",
        user_id=user.id,
        status="PENDING",
        scheduled_at=utcnow(),
    )
    session.add(event)
    return event


def enqueue_notification_email(
    session: AsyncSession, notification: Notification, user: User
) -> EmailOutbox:
    event = EmailOutbox(
        template_key="notification_email",
        delivery_type="NOTIFICATION",
        idempotency_key=f"notification:{notification.id}:email",
        user_id=user.id,
        notification_id=notification.id,
        status="PENDING",
        scheduled_at=utcnow(),
    )
    session.add(event)
    return event


async def _claim_event(
    session: AsyncSession, *, user_id: uuid.UUID | None = None
) -> EmailOutbox | None:
    statement = (
        select(EmailOutbox)
        .where(EmailOutbox.status == "PENDING", EmailOutbox.scheduled_at <= utcnow())
        .order_by(EmailOutbox.scheduled_at, EmailOutbox.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if user_id is not None:
        statement = statement.where(
            EmailOutbox.user_id == user_id, EmailOutbox.delivery_type == "WELCOME"
        )
    event = await session.scalar(statement)
    if event is None:
        return None
    event.status = "PROCESSING"
    event.processing_started_at = utcnow()
    event.attempt_count += 1
    if event.campaign_delivery_id:
        delivery = await session.get(EmailCampaignDelivery, event.campaign_delivery_id)
        if delivery:
            delivery.status = "PROCESSING"
            delivery.processing_started_at = event.processing_started_at
            delivery.attempt_count = event.attempt_count
        if event.campaign_id:
            campaign = await session.get(EmailCampaign, event.campaign_id)
            if campaign and campaign.status == "SCHEDULED":
                campaign.status = "PROCESSING"
                campaign.started_at = event.processing_started_at
                session.add(
                    AdminAuditLog(
                        actor_user_id=None,
                        action="EMAIL_CAMPAIGN_STARTED",
                        resource_type="EMAIL_CAMPAIGN",
                        resource_id=campaign.id,
                    )
                )
    await session.commit()
    return event


def _absolute_url(value: str | None) -> str:
    base = get_settings().app_base_url.rstrip("/")
    if not value:
        return base
    return value if value.startswith(("https://", "http://")) else f"{base}/{value.lstrip('/')}"


async def _send_event(session: AsyncSession, event: EmailOutbox, user: User) -> None:
    if event.delivery_type == "WELCOME":
        await send_welcome_email(session, user)
        return
    if event.delivery_type == "NOTIFICATION":
        notification = await session.get(Notification, event.notification_id)
        if notification is None:
            raise LookupError("Die Benachrichtigung ist nicht verfügbar.")
        rendered = await render_email_template(
            session,
            "notification_email",
            {
                "name": display_name(user),
                "notification_title": notification.title,
                "notification_message": notification.message,
                "action_url": _absolute_url(notification.action_url),
                "action_label": notification.action_label or "Stadtplaner öffnen",
                "category": notification.category,
            },
            preferences_url=(
                f"{get_settings().app_base_url.rstrip('/')}/profil#benachrichtigungen"
            ),
        )
        await send_rendered_email(user.email, rendered, to_name=display_name(user))
        return
    delivery = await session.get(EmailCampaignDelivery, event.campaign_delivery_id)
    campaign = await session.get(EmailCampaign, event.campaign_id)
    if delivery is None or campaign is None or delivery.status == "CANCELLED":
        raise LookupError("Die Rundmail-Zustellung ist nicht verfügbar.")
    base = get_settings().app_base_url.rstrip("/")
    unsubscribe_url = None
    headers = None
    if campaign.campaign_type == "NEWSLETTER":
        token = await create_unsubscribe_token(session, user.id)
        unsubscribe_url = f"{base}/email-abmelden?token={token}"
        api_unsubscribe_url = (
            f"{get_settings().api_base_url.rstrip('/')}/api/v1/email/unsubscribe?token={token}"
        )
        headers = {
            "List-Unsubscribe": f"<{api_unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    template = await get_template_content(session, "system_announcement")
    override = EmailTemplateContent(
        campaign.subject,
        template.html_body,
        template.text_body,
        template.customized,
        template.version,
    )
    rendered = await render_email_template(
        session,
        "system_announcement",
        {
            "name": delivery.recipient_name,
            "title": campaign.title,
            "intro": campaign.intro or "",
            "content": campaign.content_html,
            "action_url": _absolute_url(campaign.action_url),
            "action_label": campaign.action_label or "Stadtplaner öffnen",
            "app_url": base,
        },
        content_override=override,
        trusted_html_variables=frozenset({"content"}),
        text_variables={"content": campaign.content_text},
        preferences_url=f"{base}/profil#benachrichtigungen",
        unsubscribe_url=unsubscribe_url,
    )
    await send_rendered_email(
        delivery.recipient_email,
        rendered,
        to_name=delivery.recipient_name,
        headers=headers,
    )


async def _refresh_campaign_counts(session: AsyncSession, campaign_id: uuid.UUID) -> None:
    campaign = await session.get(EmailCampaign, campaign_id)
    if campaign is None:
        return
    rows = (
        await session.execute(
            select(EmailCampaignDelivery.status, func.count())
            .where(EmailCampaignDelivery.campaign_id == campaign_id)
            .group_by(EmailCampaignDelivery.status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    campaign.sent_count = counts.get("SENT", 0)
    campaign.failed_count = counts.get("FAILED", 0)
    campaign.skipped_count = counts.get("SKIPPED", 0) + counts.get("CANCELLED", 0)
    if not any(counts.get(status, 0) for status in ("PENDING", "PROCESSING")):
        was_completed = campaign.status == "COMPLETED"
        campaign.status = "COMPLETED" if campaign.status != "CANCELLED" else "CANCELLED"
        campaign.completed_at = campaign.completed_at or utcnow()
        if campaign.status == "COMPLETED" and not was_completed:
            session.add(
                AdminAuditLog(
                    actor_user_id=None,
                    action="EMAIL_CAMPAIGN_COMPLETED",
                    resource_type="EMAIL_CAMPAIGN",
                    resource_id=campaign.id,
                    event_metadata={
                        "recipient_count": campaign.recipient_count,
                        "sent_count": campaign.sent_count,
                        "failed_count": campaign.failed_count,
                    },
                )
            )


async def _finish_event(session: AsyncSession, event_id: uuid.UUID) -> bool:
    event = await session.scalar(
        select(EmailOutbox).where(EmailOutbox.id == event_id).with_for_update()
    )
    if event is None or event.status != "PROCESSING":
        return False
    delivery_type = event.delivery_type or (
        "WELCOME" if event.template_key == "welcome" else "CAMPAIGN"
    )
    user = await session.scalar(select(User).where(User.id == event.user_id).with_for_update())
    if user is None:
        event.status = "FAILED"
        event.processing_started_at = None
        event.last_error = "Empfängerkonto nicht verfügbar"
        if event.campaign_delivery_id:
            delivery = await session.get(EmailCampaignDelivery, event.campaign_delivery_id)
            if delivery:
                delivery.status = "SKIPPED"
                delivery.processing_started_at = None
                delivery.last_error = "Empfängerkonto nicht verfügbar"
            if event.campaign_id:
                await _refresh_campaign_counts(session, event.campaign_id)
        await session.commit()
        return False
    if delivery_type == "WELCOME" and user.welcome_email_sent_at is not None:
        event.status = "SENT"
        event.sent_at = user.welcome_email_sent_at
        event.processing_started_at = None
        await session.commit()
        return True
    try:
        event.delivery_type = delivery_type
        await _send_event(session, event, user)
    except (
        EmailTemplateValidationError,
        LookupError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
        ValueError,
    ) as exc:
        await session.rollback()
        failed = await session.scalar(
            select(EmailOutbox).where(EmailOutbox.id == event_id).with_for_update()
        )
        if failed is None:
            return False
        permanent = isinstance(exc, (LookupError, smtplib.SMTPRecipientsRefused))
        max_attempts = getattr(get_settings(), "email_outbox_max_attempts", 8)
        failed.status = "FAILED" if permanent or failed.attempt_count >= max_attempts else "PENDING"
        failed.processing_started_at = None
        failed.last_error = type(exc).__name__
        if failed.status == "PENDING":
            index = min(failed.attempt_count - 1, len(RETRY_DELAYS) - 1)
            failed.scheduled_at = utcnow() + timedelta(seconds=RETRY_DELAYS[index])
        if failed.campaign_delivery_id:
            delivery = await session.get(EmailCampaignDelivery, failed.campaign_delivery_id)
            if delivery:
                delivery.status = failed.status
                delivery.processing_started_at = None
                delivery.attempt_count = failed.attempt_count
                delivery.last_error = failed.last_error
            await _refresh_campaign_counts(session, failed.campaign_id)
        session.add(
            AdminAuditLog(
                actor_user_id=None,
                target_user_id=failed.user_id,
                action=(
                    "WELCOME_EMAIL_FAILED"
                    if failed.delivery_type == "WELCOME"
                    else "EMAIL_DELIVERY_FAILED"
                ),
                resource_type="EMAIL_OUTBOX",
                resource_id=failed.id,
                event_metadata={
                    "delivery_type": failed.delivery_type,
                    "attempt_count": failed.attempt_count,
                },
            )
        )
        await session.commit()
        logger.error(
            "Email delivery failed outbox_id=%s error_type=%s",
            failed.id,
            type(exc).__name__,
        )
        return False
    sent_at = utcnow()
    event.status = "SENT"
    event.sent_at = sent_at
    event.processing_started_at = None
    event.last_error = None
    if delivery_type == "WELCOME":
        user.welcome_email_sent_at = sent_at
        action = "WELCOME_EMAIL_SENT"
    else:
        action = "EMAIL_DELIVERY_SENT"
    if event.campaign_delivery_id:
        delivery = await session.get(EmailCampaignDelivery, event.campaign_delivery_id)
        if delivery:
            delivery.status = "SENT"
            delivery.sent_at = sent_at
            delivery.processing_started_at = None
            delivery.last_error = None
        await _refresh_campaign_counts(session, event.campaign_id)
    session.add(
        AdminAuditLog(
            actor_user_id=None,
            target_user_id=user.id,
            action=action,
            resource_type="EMAIL_OUTBOX",
            resource_id=event.id,
            event_metadata={
                "delivery_type": delivery_type,
                "attempt_count": event.attempt_count,
            },
        )
    )
    await session.commit()
    return True


async def _finish_welcome_event(session: AsyncSession, event_id: uuid.UUID) -> bool:
    return await _finish_event(session, event_id)


async def attempt_welcome_delivery(session: AsyncSession, user_id: uuid.UUID) -> bool:
    try:
        event = await _claim_event(session, user_id=user_id)
        return bool(event and await _finish_event(session, event.id))
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        await session.rollback()
        logger.error(
            "Welcome delivery start failed user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return False


async def process_due_email_outbox(session: AsyncSession, *, limit: int = 20) -> dict[str, int]:
    stale_before = utcnow() - timedelta(minutes=15)
    stale = (
        await session.scalars(
            select(EmailOutbox).where(
                EmailOutbox.status == "PROCESSING",
                or_(
                    EmailOutbox.processing_started_at.is_(None),
                    EmailOutbox.processing_started_at < stale_before,
                ),
            )
        )
    ).all()
    for event in stale:
        event.status = "PENDING"
        event.processing_started_at = None
        event.scheduled_at = utcnow()
    await session.commit()
    result = {"processed": 0, "sent": 0, "failed": 0}
    for _ in range(limit):
        event = await _claim_event(session)
        if event is None:
            break
        result["processed"] += 1
        result["sent" if await _finish_event(session, event.id) else "failed"] += 1
    return result

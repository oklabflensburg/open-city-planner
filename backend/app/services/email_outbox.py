import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.email_outbox import EmailOutbox
from app.models.user import User
from app.services.email_service import EmailTemplateValidationError, send_welcome_email

logger = logging.getLogger(__name__)
WELCOME_TEMPLATE_KEY = "welcome"
RETRY_DELAYS = (60, 300, 1_800, 7_200, 21_600, 86_400)


def utcnow() -> datetime:
    return datetime.now(UTC)


def enqueue_welcome_email(session: AsyncSession, user: User) -> EmailOutbox | None:
    if not user.is_verified or user.welcome_email_sent_at is not None:
        return None
    event = EmailOutbox(
        template_key=WELCOME_TEMPLATE_KEY,
        user_id=user.id,
        status="PENDING",
        scheduled_at=utcnow(),
    )
    session.add(event)
    return event


async def _claim_welcome_event(
    session: AsyncSession, *, user_id: uuid.UUID | None = None
) -> EmailOutbox | None:
    statement = (
        select(EmailOutbox)
        .where(
            EmailOutbox.template_key == WELCOME_TEMPLATE_KEY,
            EmailOutbox.status == "PENDING",
            EmailOutbox.scheduled_at <= utcnow(),
        )
        .order_by(EmailOutbox.scheduled_at, EmailOutbox.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if user_id is not None:
        statement = statement.where(EmailOutbox.user_id == user_id)
    event = await session.scalar(statement)
    if event is None:
        return None
    event.status = "PROCESSING"
    event.processing_started_at = utcnow()
    event.attempt_count += 1
    await session.commit()
    return event


async def _finish_welcome_event(session: AsyncSession, event_id: uuid.UUID) -> bool:
    event = await session.scalar(
        select(EmailOutbox).where(EmailOutbox.id == event_id).with_for_update()
    )
    if event is None or event.status != "PROCESSING":
        return False
    user = await session.scalar(select(User).where(User.id == event.user_id).with_for_update())
    if user is None or not user.is_verified:
        event.status = "FAILED"
        event.processing_started_at = None
        event.last_error = "Das zugehörige bestätigte Konto ist nicht verfügbar."
        await session.commit()
        return False
    if user.welcome_email_sent_at is not None:
        event.status = "SENT"
        event.sent_at = user.welcome_email_sent_at
        event.processing_started_at = None
        event.last_error = None
        await session.commit()
        return True
    try:
        await send_welcome_email(session, user)
    except (
        EmailTemplateValidationError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
        ValueError,
    ) as exc:
        await session.rollback()
        failed_event = await session.scalar(
            select(EmailOutbox).where(EmailOutbox.id == event_id).with_for_update()
        )
        if failed_event is None:
            return False
        failed_event.processing_started_at = None
        failed_event.last_error = type(exc).__name__
        delay_index = min(failed_event.attempt_count - 1, len(RETRY_DELAYS) - 1)
        failed_event.status = "PENDING"
        failed_event.scheduled_at = utcnow() + timedelta(seconds=RETRY_DELAYS[delay_index])
        session.add(
            AdminAuditLog(
                actor_user_id=None,
                target_user_id=failed_event.user_id,
                action="WELCOME_EMAIL_FAILED",
                resource_type="EMAIL_OUTBOX",
                resource_id=failed_event.id,
                event_metadata={"attempt_count": failed_event.attempt_count},
            )
        )
        await session.commit()
        logger.error(
            "Welcome email delivery failed outbox_id=%s attempt=%s error_type=%s",
            failed_event.id,
            failed_event.attempt_count,
            type(exc).__name__,
        )
        return False
    sent_at = utcnow()
    event.status = "SENT"
    event.sent_at = sent_at
    event.processing_started_at = None
    event.last_error = None
    user.welcome_email_sent_at = sent_at
    session.add(
        AdminAuditLog(
            actor_user_id=None,
            target_user_id=user.id,
            action="WELCOME_EMAIL_SENT",
            resource_type="EMAIL_OUTBOX",
            resource_id=event.id,
            event_metadata={"attempt_count": event.attempt_count},
        )
    )
    await session.commit()
    return True


async def attempt_welcome_delivery(session: AsyncSession, user_id: uuid.UUID) -> bool:
    try:
        event = await _claim_welcome_event(session, user_id=user_id)
        return bool(event and await _finish_welcome_event(session, event.id))
    except (OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
        await session.rollback()
        logger.error(
            "Welcome email delivery could not be started for user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return False


async def process_due_email_outbox(session: AsyncSession, *, limit: int = 20) -> dict[str, int]:
    stale_before = utcnow() - timedelta(minutes=15)
    stale_events = (
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
    for event in stale_events:
        event.status = "PENDING"
        event.processing_started_at = None
        event.scheduled_at = utcnow()
    await session.commit()

    result = {"processed": 0, "sent": 0, "failed": 0}
    for _ in range(limit):
        event = await _claim_welcome_event(session)
        if event is None:
            break
        result["processed"] += 1
        if await _finish_welcome_event(session, event.id):
            result["sent"] += 1
        else:
            result["failed"] += 1
    return result

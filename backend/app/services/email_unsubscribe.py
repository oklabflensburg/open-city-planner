import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import generate_token, hash_token
from app.models.admin_audit_log import AdminAuditLog
from app.models.email_unsubscribe import EmailUnsubscribeToken
from app.models.notification import NotificationPreference


async def create_unsubscribe_token(
    session: AsyncSession, user_id: uuid.UUID, *, scope: str = "newsletter"
) -> str:
    token = generate_token()
    session.add(EmailUnsubscribeToken(token_hash=hash_token(token), user_id=user_id, scope=scope))
    await session.flush()
    return token


async def unsubscribe_newsletter(session: AsyncSession, token: str) -> bool:
    record = await session.scalar(
        select(EmailUnsubscribeToken)
        .where(EmailUnsubscribeToken.token_hash == hash_token(token))
        .with_for_update()
    )
    if record is None or record.scope != "newsletter":
        return False
    preferences = await session.get(NotificationPreference, record.user_id)
    if preferences is None:
        preferences = NotificationPreference(user_id=record.user_id)
        session.add(preferences)
    changed = bool(preferences.newsletter_enabled)
    preferences.newsletter_enabled = False
    record.used_at = record.used_at or datetime.now(UTC)
    if changed:
        session.add(
            AdminAuditLog(
                actor_user_id=None,
                target_user_id=record.user_id,
                action="NEWSLETTER_UNSUBSCRIBED",
                resource_type="USER",
                resource_id=record.user_id,
            )
        )
    await session.commit()
    return True

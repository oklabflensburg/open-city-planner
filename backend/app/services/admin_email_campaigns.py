import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.email_campaign import EmailCampaign, EmailCampaignDelivery
from app.models.email_outbox import EmailOutbox
from app.models.notification import NotificationPreference
from app.models.user import User
from app.services.email_service import (
    EmailTemplateContent,
    display_name,
    get_template_content,
    render_email_template,
    sanitize_email_html,
    send_rendered_email,
)


class CampaignConflict(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value
    if parsed.scheme == "http" and parsed.netloc and not get_settings().production:
        return value
    raise ValueError("Die Aktions-URL muss intern oder eine sichere HTTPS-URL sein.")


def _clean(data: dict) -> dict:
    subject = str(data["subject"]).strip()
    internal_name = str(data["internal_name"]).strip()
    title = str(data["title"]).strip()
    content_html = sanitize_email_html(str(data["content_html"]).strip())
    content_text = str(data["content_text"]).strip()
    if not all((internal_name, subject, title, content_html, content_text)):
        raise ValueError("Name, Betreff, Titel sowie HTML- und Textinhalt sind erforderlich.")
    if "\r" in subject or "\n" in subject:
        raise ValueError("Der Betreff darf keinen Zeilenumbruch enthalten.")
    return {
        **data,
        "internal_name": internal_name,
        "subject": subject,
        "title": title,
        "intro": str(data.get("intro") or "").strip() or None,
        "content_html": content_html,
        "content_text": content_text,
        "action_url": _validate_url(data.get("action_url")),
        "action_label": str(data.get("action_label") or "").strip() or None,
    }


async def list_campaigns(session: AsyncSession) -> list[EmailCampaign]:
    return list(
        await session.scalars(select(EmailCampaign).order_by(EmailCampaign.created_at.desc()))
    )


async def get_campaign(session: AsyncSession, campaign_id: uuid.UUID) -> EmailCampaign:
    campaign = await session.get(EmailCampaign, campaign_id)
    if campaign is None:
        raise LookupError("Die Rundmail wurde nicht gefunden.")
    return campaign


async def create_campaign(session: AsyncSession, data: dict, actor: User) -> EmailCampaign:
    values = _clean(data)
    values.pop("version", None)
    campaign = EmailCampaign(
        **values,
        status="DRAFT",
        created_by_user_id=actor.id,
        updated_by_user_id=actor.id,
    )
    session.add(campaign)
    await session.flush()
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_CAMPAIGN_CREATED",
            resource_type="EMAIL_CAMPAIGN",
            resource_id=campaign.id,
            event_metadata={"campaign_type": campaign.campaign_type},
        )
    )
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def update_campaign(
    session: AsyncSession, campaign_id: uuid.UUID, data: dict, actor: User
) -> EmailCampaign:
    campaign = await session.scalar(
        select(EmailCampaign).where(EmailCampaign.id == campaign_id).with_for_update()
    )
    if campaign is None:
        raise LookupError("Die Rundmail wurde nicht gefunden.")
    if campaign.status != "DRAFT":
        raise CampaignConflict("Eine gestartete Rundmail kann nicht mehr geändert werden.")
    expected = data.get("version")
    if expected != campaign.version:
        raise CampaignConflict("Die Rundmail wurde zwischenzeitlich geändert.")
    values = _clean(data)
    values.pop("version", None)
    for key, value in values.items():
        setattr(campaign, key, value)
    campaign.version += 1
    campaign.updated_by_user_id = actor.id
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_CAMPAIGN_UPDATED",
            resource_type="EMAIL_CAMPAIGN",
            resource_id=campaign.id,
            event_metadata={"version": campaign.version},
        )
    )
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def render_campaign(session: AsyncSession, campaign: EmailCampaign, name: str):
    template = await get_template_content(session, "system_announcement")
    override = EmailTemplateContent(
        campaign.subject,
        template.html_body,
        template.text_body,
        template.customized,
        template.version,
    )
    base = get_settings().app_base_url.rstrip("/")
    return await render_email_template(
        session,
        "system_announcement",
        {
            "name": name,
            "title": campaign.title,
            "intro": campaign.intro or "",
            "content": campaign.content_html,
            "action_url": campaign.action_url or base,
            "action_label": campaign.action_label or "Stadtplaner öffnen",
            "app_url": base,
        },
        content_override=override,
        trusted_html_variables=frozenset({"content"}),
        text_variables={"content": campaign.content_text},
    )


async def preview_campaign(session: AsyncSession, campaign: EmailCampaign):
    return await render_campaign(session, campaign, "Max Mustermann")


async def test_campaign(session: AsyncSession, campaign: EmailCampaign, actor: User) -> None:
    rendered = await render_campaign(session, campaign, display_name(actor))
    await send_rendered_email(actor.email, rendered, to_name=display_name(actor))
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_CAMPAIGN_TEST_SENT",
            resource_type="EMAIL_CAMPAIGN",
            resource_id=campaign.id,
        )
    )
    await session.commit()


def _recipient_query(campaign: EmailCampaign):
    statement = select(User).where(User.is_active.is_(True), User.email_pending.is_(False))
    if campaign.recipient_scope == "VERIFIED_USERS":
        statement = statement.where(User.is_verified.is_(True))
    elif campaign.recipient_scope == "SUPERUSERS":
        statement = statement.where(User.is_superuser.is_(True), User.is_verified.is_(True))
    return statement.order_by(User.id)


async def campaign_recipient_count(session: AsyncSession, campaign: EmailCampaign) -> int:
    users = list(await session.scalars(_recipient_query(campaign)))
    if campaign.campaign_type != "NEWSLETTER":
        return len(users)
    enabled = set(
        await session.scalars(
            select(NotificationPreference.user_id).where(
                NotificationPreference.user_id.in_([user.id for user in users]),
                NotificationPreference.newsletter_enabled.is_(True),
            )
        )
    )
    return sum(user.id in enabled for user in users)


async def start_campaign(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    actor: User,
    *,
    legal_confirmed: bool,
) -> EmailCampaign:
    campaign = await session.scalar(
        select(EmailCampaign).where(EmailCampaign.id == campaign_id).with_for_update()
    )
    if campaign is None:
        raise LookupError("Die Rundmail wurde nicht gefunden.")
    if campaign.status in {"SCHEDULED", "PROCESSING", "COMPLETED"}:
        return campaign
    if campaign.status != "DRAFT":
        raise CampaignConflict("Diese Rundmail kann nicht gestartet werden.")
    if campaign.campaign_type == "LEGAL" and not legal_confirmed:
        raise CampaignConflict("Die rechtliche Klassifizierung muss ausdrücklich bestätigt werden.")
    users = list(await session.scalars(_recipient_query(campaign)))
    if campaign.campaign_type == "NEWSLETTER":
        enabled = set(
            await session.scalars(
                select(NotificationPreference.user_id).where(
                    NotificationPreference.user_id.in_([user.id for user in users]),
                    NotificationPreference.newsletter_enabled.is_(True),
                )
            )
        )
        users = [user for user in users if user.id in enabled]
    due = campaign.scheduled_at or utcnow()
    for user in users:
        delivery_id = uuid.uuid4()
        delivery = EmailCampaignDelivery(
            id=delivery_id,
            campaign_id=campaign.id,
            user_id=user.id,
            recipient_email=user.email,
            recipient_name=display_name(user),
            status="PENDING",
            scheduled_at=due,
        )
        session.add(delivery)
        session.add(
            EmailOutbox(
                template_key="system_announcement",
                delivery_type="CAMPAIGN",
                idempotency_key=f"campaign:{campaign.id}:{user.id}",
                user_id=user.id,
                campaign_id=campaign.id,
                campaign_delivery_id=delivery_id,
                status="PENDING",
                scheduled_at=due,
            )
        )
    scheduled = bool(users and campaign.scheduled_at and campaign.scheduled_at > utcnow())
    campaign.status = "SCHEDULED" if scheduled else "PROCESSING" if users else "COMPLETED"
    campaign.started_at = None if scheduled else utcnow()
    campaign.completed_at = None if users else utcnow()
    campaign.recipient_count = len(users)
    action = "EMAIL_CAMPAIGN_STARTED"
    if scheduled:
        action = "EMAIL_CAMPAIGN_SCHEDULED"
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action=action,
            resource_type="EMAIL_CAMPAIGN",
            resource_id=campaign.id,
            event_metadata={"recipient_count": len(users), "campaign_type": campaign.campaign_type},
        )
    )
    if not users:
        session.add(
            AdminAuditLog(
                actor_user_id=None,
                action="EMAIL_CAMPAIGN_COMPLETED",
                resource_type="EMAIL_CAMPAIGN",
                resource_id=campaign.id,
                event_metadata={"recipient_count": 0, "sent_count": 0, "failed_count": 0},
            )
        )
    if campaign.campaign_type == "LEGAL":
        session.add(
            AdminAuditLog(
                actor_user_id=actor.id,
                action="EMAIL_CAMPAIGN_LEGAL_CONFIRMED",
                resource_type="EMAIL_CAMPAIGN",
                resource_id=campaign.id,
            )
        )
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def cancel_campaign(
    session: AsyncSession, campaign_id: uuid.UUID, actor: User
) -> EmailCampaign:
    campaign = await session.scalar(
        select(EmailCampaign).where(EmailCampaign.id == campaign_id).with_for_update()
    )
    if campaign is None:
        raise LookupError("Die Rundmail wurde nicht gefunden.")
    if campaign.status == "COMPLETED":
        raise CampaignConflict("Eine abgeschlossene Rundmail kann nicht abgebrochen werden.")
    await session.execute(
        update(EmailCampaignDelivery)
        .where(
            EmailCampaignDelivery.campaign_id == campaign.id,
            EmailCampaignDelivery.status == "PENDING",
        )
        .values(status="CANCELLED")
    )
    await session.execute(
        update(EmailOutbox)
        .where(EmailOutbox.campaign_id == campaign.id, EmailOutbox.status == "PENDING")
        .values(status="CANCELLED")
    )
    campaign.status = "CANCELLED"
    campaign.completed_at = utcnow()
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_CAMPAIGN_CANCELLED",
            resource_type="EMAIL_CAMPAIGN",
            resource_id=campaign.id,
        )
    )
    await session.commit()
    await session.refresh(campaign)
    return campaign

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.services.email_service import (
    EMAIL_TEMPLATE_REGISTRY,
    EmailTemplateContent,
    RenderedEmail,
    default_template_content,
    render_email_template,
    send_rendered_email,
    template_definition,
    validate_template_content,
)


class EmailTemplateVersionConflict(ValueError):
    pass


@dataclass(frozen=True)
class EffectiveEmailTemplate:
    key: str
    name: str
    description: str
    category: str
    subject: str
    html_body: str
    text_body: str
    allowed_variables: list[str]
    required_variables: list[str]
    customized: bool
    version: int
    active: bool
    security_sensitive: bool
    updated_at: datetime | None
    updated_by: str | None


def preview_variables(key: str) -> dict[str, str]:
    values = {
        "name": "Max Mustermann",
        "app_url": "https://example.invalid",
        "documentation_url": "https://example.invalid/dokumentation",
        "profile_url": "https://example.invalid/profil",
        "verification_url": "https://example.invalid/email-bestaetigen?token=vorschau",
        "reset_url": "https://example.invalid/passwort-zuruecksetzen?token=vorschau",
        "expires_minutes": "60",
        "security_event_title": "Sicherheitseinstellung geändert",
        "security_event_message": "Dies ist eine sichere Vorschau ohne echte Kontodaten.",
        "email": "max.mustermann@example.invalid",
        "subject": "Beispielanfrage",
        "message": "Dies ist ein Beispieltext für die Vorschau.",
        "received_at": "19.08.2026, 12:00 MESZ",
    }
    return {name: values[name] for name in template_definition(key).allowed_variables}


async def _records(session: AsyncSession) -> dict[str, EmailTemplate]:
    rows = await session.scalars(select(EmailTemplate))
    return {row.key: row for row in rows}


async def _effective(
    session: AsyncSession, key: str, records: dict[str, EmailTemplate] | None = None
) -> EffectiveEmailTemplate:
    definition = template_definition(key)
    record = (records or await _records(session)).get(key)
    content = (
        EmailTemplateContent(
            record.subject,
            record.html_body,
            record.text_body,
            record.is_customized,
            record.version,
        )
        if record
        else default_template_content(definition)
    )
    updated_by = None
    if record and record.updated_by_user_id:
        user = await session.get(User, record.updated_by_user_id)
        if user:
            updated_by = user.display_name or user.email
    return EffectiveEmailTemplate(
        key=key,
        name=definition.name,
        description=definition.description,
        category=definition.category,
        subject=content.subject,
        html_body=content.html_body,
        text_body=content.text_body,
        allowed_variables=sorted(definition.allowed_variables),
        required_variables=sorted(definition.required_variables),
        customized=content.customized,
        version=content.version,
        active=definition.is_active,
        security_sensitive=definition.is_security_sensitive,
        updated_at=record.updated_at if record else None,
        updated_by=updated_by,
    )


async def list_email_templates(session: AsyncSession) -> list[EffectiveEmailTemplate]:
    records = await _records(session)
    return [
        await _effective(session, key, records)
        for key in EMAIL_TEMPLATE_REGISTRY
    ]


async def get_email_template(session: AsyncSession, key: str) -> EffectiveEmailTemplate:
    return await _effective(session, key)


async def _locked_record(session: AsyncSession, key: str) -> EmailTemplate | None:
    return await session.scalar(
        select(EmailTemplate).where(EmailTemplate.key == key).with_for_update()
    )


async def update_email_template(
    session: AsyncSession,
    key: str,
    *,
    subject: str,
    html_body: str,
    text_body: str,
    expected_version: int,
    actor: User,
) -> EffectiveEmailTemplate:
    definition = template_definition(key)
    subject, html_body, text_body = validate_template_content(
        definition, subject, html_body, text_body
    )
    record = await _locked_record(session, key)
    current_version = record.version if record else 0
    if current_version != expected_version:
        raise EmailTemplateVersionConflict
    customized = (
        subject != definition.default_subject
        or html_body != validate_template_content(
            definition,
            definition.default_subject,
            definition.default_html,
            definition.default_text,
        )[1]
        or text_body != definition.default_text
    )
    if record is None:
        record = EmailTemplate(
            key=key,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            is_customized=customized,
            version=1,
            updated_by_user_id=actor.id,
        )
        session.add(record)
    else:
        record.subject = subject
        record.html_body = html_body
        record.text_body = text_body
        record.is_customized = customized
        record.version += 1
        record.updated_by_user_id = actor.id
    await session.flush()
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_TEMPLATE_UPDATED",
            resource_type="SYSTEM",
            resource_id=record.id,
            event_metadata={
                "template_key": key,
                "version": record.version,
                "changed_fields": ["subject", "html_body", "text_body"],
            },
        )
    )
    await session.commit()
    await session.refresh(record)
    return await _effective(session, key, {key: record})


async def reset_email_template(
    session: AsyncSession, key: str, *, expected_version: int, actor: User
) -> EffectiveEmailTemplate:
    definition = template_definition(key)
    record = await _locked_record(session, key)
    current_version = record.version if record else 0
    if current_version != expected_version:
        raise EmailTemplateVersionConflict
    if record is None:
        record = EmailTemplate(
            key=key,
            subject=definition.default_subject,
            html_body=definition.default_html,
            text_body=definition.default_text,
            is_customized=False,
            version=1,
            updated_by_user_id=actor.id,
        )
        session.add(record)
    else:
        record.subject = definition.default_subject
        record.html_body = definition.default_html
        record.text_body = definition.default_text
        record.is_customized = False
        record.version += 1
        record.updated_by_user_id = actor.id
    await session.flush()
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_TEMPLATE_RESET",
            resource_type="SYSTEM",
            resource_id=record.id,
            event_metadata={"template_key": key, "version": record.version},
        )
    )
    await session.commit()
    await session.refresh(record)
    return await _effective(session, key, {key: record})


async def preview_email_template(
    session: AsyncSession,
    key: str,
    *,
    subject: str,
    html_body: str,
    text_body: str,
    version: int,
) -> RenderedEmail:
    return await render_email_template(
        session,
        key,
        preview_variables(key),
        content_override=EmailTemplateContent(
            subject, html_body, text_body, True, version
        ),
    )


async def send_test_email(
    session: AsyncSession,
    key: str,
    *,
    subject: str,
    html_body: str,
    text_body: str,
    version: int,
    actor: User,
) -> None:
    rendered = await preview_email_template(
        session,
        key,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        version=version,
    )
    await send_rendered_email(actor.email, rendered, to_name=actor.display_name)
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            action="EMAIL_TEMPLATE_TEST_SENT",
            resource_type="SYSTEM",
            event_metadata={"template_key": key, "version": version},
        )
    )
    await session.commit()

import math
import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.admin_audit_log import AdminAuditLog
from app.models.user import User
from app.schemas.admin import (
    AuditLogActor,
    AuditLogListItem,
    AuditLogListRead,
    AuditLogResource,
)

REDACTED = "[REDACTED]"
_SENSITIVE_PARTS = {
    "password",
    "passwordhash",
    "token",
    "accesstoken",
    "refreshtoken",
    "csrftoken",
    "secret",
    "clientsecret",
    "resettoken",
    "emailverificationtoken",
    "apikey",
    "authorization",
    "authorizationcode",
    "codeverifier",
    "clientid",
    "challenge",
    "credential",
    "publickey",
    "clientdata",
    "attestation",
    "signature",
    "userhandle",
}


def redact_audit_metadata(value: Any) -> Any:
    """Recursively remove authentication material before an audit DTO is returned."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            result[str(key)] = (
                REDACTED
                if any(part in normalized for part in _SENSITIVE_PARTS)
                else redact_audit_metadata(item)
            )
        return result
    if isinstance(value, list):
        return [redact_audit_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [redact_audit_metadata(item) for item in value]
    return value


def _display_name(user: User | None) -> str | None:
    if not user:
        return None
    return (
        user.display_name
        or " ".join(part for part in (user.first_name, user.last_name) if part)
        or user.email
    )


def _summary(log: AdminAuditLog, target: User | None) -> str:
    label = _display_name(target) or "gelöschtes Benutzerkonto"
    role = f" ({log.role})" if log.role else ""
    login_blocked_summary = (
        "Anmeldung wurde blockiert, da das Benutzerkonto zuvor selbst deaktiviert wurde."
        if (log.event_metadata or {}).get("reason") == "SELF_DEACTIVATED"
        else "Anmeldung wurde blockiert, da das Benutzerkonto deaktiviert ist."
    )
    summaries = {
        "USER_ROLE_ASSIGNED": f"Rolle{role} wurde {label} zugewiesen.",
        "USER_ROLE_REMOVED": f"Rolle{role} wurde {label} entzogen.",
        "USER_ACTIVATED": f"Benutzerkonto {label} wurde aktiviert.",
        "USER_DEACTIVATED": f"Benutzerkonto {label} wurde deaktiviert.",
        "ACCOUNT_DEACTIVATED": "Benutzerkonto wurde durch den Benutzer selbst deaktiviert.",
        "ACCOUNT_DELETED": "Benutzerkonto wurde auf Wunsch des Benutzers dauerhaft gelöscht.",
        "LOGIN_BLOCKED": login_blocked_summary,
        "USER_SUPERUSER_GRANTED_DIRECT": f"Superuser-Status wurde {label} direkt zugewiesen.",
        "REFRESH_TOKEN_REUSE_DETECTED": f"Wiederverwendung eines Refresh-Tokens für {label} wurde erkannt.",
        "OAUTH_LOGIN_SUCCESS": f"Anmeldung über ein externes Konto für {label} war erfolgreich.",
        "OAUTH_LOGIN_FAILED": "Eine externe Anmeldung ist fehlgeschlagen oder wurde abgebrochen.",
        "OAUTH_ACCOUNT_LINKED": f"Ein externes Konto wurde mit {label} verknüpft.",
        "OAUTH_ACCOUNT_LINK_FAILED": f"Ein externes Konto konnte nicht mit {label} verknüpft werden.",
        "OAUTH_ACCOUNT_UNLINKED": f"Eine externe Kontoverknüpfung von {label} wurde entfernt.",
        "EMAIL_CAMPAIGN_CREATED": "Eine Rundmail wurde als Entwurf angelegt.",
        "EMAIL_CAMPAIGN_UPDATED": "Ein Rundmail-Entwurf wurde geändert.",
        "EMAIL_CAMPAIGN_SCHEDULED": "Der Rundmail-Versand wurde geplant.",
        "EMAIL_CAMPAIGN_STARTED": "Der Rundmail-Versand wurde gestartet.",
        "EMAIL_CAMPAIGN_CANCELLED": "Der Rundmail-Versand wurde abgebrochen.",
        "EMAIL_CAMPAIGN_COMPLETED": "Der Rundmail-Versand wurde abgeschlossen.",
        "EMAIL_CAMPAIGN_LEGAL_CONFIRMED": "Die Klassifizierung als notwendige Mitteilung wurde bestätigt.",
        "EMAIL_CAMPAIGN_TEST_SENT": "Eine Rundmail-Testnachricht wurde versendet.",
        "EMAIL_PREFERENCE_UPDATED": f"Die E-Mail-Einstellungen von {label} wurden geändert.",
        "NEWSLETTER_UNSUBSCRIBED": f"Der Newsletter wurde für {label} abbestellt.",
        "NEWSLETTER_RESUBSCRIBED": f"Der Newsletter wurde für {label} wieder aktiviert.",
        "EMAIL_DELIVERY_SENT": f"Eine E-Mail an {label} wurde versendet.",
        "EMAIL_DELIVERY_FAILED": f"Eine E-Mail an {label} konnte nicht versendet werden.",
        "WELCOME_EMAIL_SENT": f"Die Willkommensmail an {label} wurde versendet.",
        "WELCOME_EMAIL_FAILED": f"Die Willkommensmail an {label} konnte nicht versendet werden.",
        "MFA_SETUP_STARTED": f"Die Einrichtung der Zwei-Faktor-Authentifizierung für {label} wurde begonnen.",
        "MFA_ENABLED": f"Zwei-Faktor-Authentifizierung wurde für {label} aktiviert.",
        "MFA_DISABLED": f"Zwei-Faktor-Authentifizierung wurde für {label} deaktiviert.",
        "MFA_LOGIN_SUCCESS": f"Die Zwei-Faktor-Anmeldung für {label} war erfolgreich.",
        "MFA_LOGIN_FAILED": f"Eine Zwei-Faktor-Anmeldung für {label} ist fehlgeschlagen.",
        "MFA_RECOVERY_CODE_USED": f"Ein Wiederherstellungscode von {label} wurde verwendet.",
        "MFA_RECOVERY_CODES_REGENERATED": f"Neue Wiederherstellungscodes wurden für {label} erzeugt.",
        "MFA_CHALLENGE_BLOCKED": f"Eine Zwei-Faktor-Anmeldung für {label} wurde nach zu vielen Versuchen gesperrt.",
        "PASSKEY_REGISTRATION_STARTED": f"Die Passkey-Einrichtung für {label} wurde begonnen.",
        "PASSKEY_REGISTERED": f"Ein Passkey wurde für {label} registriert.",
        "PASSKEY_REGISTRATION_FAILED": f"Ein Passkey konnte für {label} nicht registriert werden.",
        "PASSKEY_LOGIN_SUCCESS": f"Die Passkey-Anmeldung für {label} war erfolgreich.",
        "PASSKEY_LOGIN_FAILED": f"Eine Passkey-Anmeldung für {label} ist fehlgeschlagen.",
        "PASSKEY_MFA_SUCCESS": f"Die Passkey-Sicherheitsbestätigung für {label} war erfolgreich.",
        "PASSKEY_MFA_FAILED": f"Die Passkey-Sicherheitsbestätigung für {label} ist fehlgeschlagen.",
        "PASSKEY_COUNTER_REGRESSION": f"Ein auffälliger Passkey-Signaturzähler wurde für {label} protokolliert.",
        "PASSKEY_RENAMED": f"Ein Passkey von {label} wurde umbenannt.",
        "PASSKEY_REMOVED": f"Ein Passkey von {label} wurde entfernt.",
        "POLYGON_DELETED": f"Die Fläche {(log.event_metadata or {}).get('title') or log.resource_id} wurde gelöscht.",
    }
    return summaries.get(log.action, f"Administrative Aktion {log.action} für {label}.")


def _serialize(log: AdminAuditLog, actor: User | None, target: User | None) -> AuditLogListItem:
    actor_dto = (
        AuditLogActor(
            id=actor.id,
            display_name=_display_name(actor),
            email=actor.email,
        )
        if actor
        else None
    )
    resource_type = log.resource_type or "USER"
    if resource_type == "POLYGON":
        resource_label = str((log.event_metadata or {}).get("title") or "Gelöschte Fläche")
    elif resource_type == "SYSTEM":
        resource_label = "Systemereignis"
    else:
        resource_label = _display_name(target) or "Gelöschtes Benutzerkonto"
    resource = AuditLogResource(
        type=resource_type,
        id=log.resource_id or log.target_user_id,
        label=resource_label,
    )
    details = redact_audit_metadata(
        {**(log.event_metadata or {}), **({"role": log.role} if log.role else {})}
    )
    return AuditLogListItem(
        id=log.id,
        created_at=log.created_at,
        action=log.action,
        actor=actor_dto,
        resource=resource,
        summary=_summary(log, target),
        details=details,
    )


async def list_audit_logs(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    action: str | None,
    user_id: uuid.UUID | None,
    resource_type: str | None,
    resource_id: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
    search: str | None,
) -> AuditLogListRead:
    actor = aliased(User, name="audit_actor")
    target = aliased(User, name="audit_target")
    filters = []
    if action:
        filters.append(AdminAuditLog.action == action.strip())
    if user_id:
        filters.append(AdminAuditLog.actor_user_id == user_id)
    if resource_id:
        filters.append(
            or_(
                AdminAuditLog.target_user_id == resource_id,
                AdminAuditLog.resource_id == resource_id,
            )
        )
    if resource_type:
        normalized_type = resource_type.upper()
        if normalized_type == "USER":
            filters.append(
                or_(
                    AdminAuditLog.resource_type == "USER",
                    AdminAuditLog.resource_type.is_(None),
                )
            )
        else:
            filters.append(AdminAuditLog.resource_type == normalized_type)
    if date_from:
        filters.append(AdminAuditLog.created_at >= date_from)
    if date_to:
        filters.append(AdminAuditLog.created_at <= date_to)
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        filters.append(
            or_(
                AdminAuditLog.action.ilike(pattern),
                AdminAuditLog.role.ilike(pattern),
                actor.email.ilike(pattern),
                target.email.ilike(pattern),
                actor.display_name.ilike(pattern),
                target.display_name.ilike(pattern),
                func.concat(actor.first_name, " ", actor.last_name).ilike(pattern),
                func.concat(target.first_name, " ", target.last_name).ilike(pattern),
                cast(AdminAuditLog.target_user_id, String).ilike(pattern),
                cast(AdminAuditLog.resource_id, String).ilike(pattern),
            )
        )

    joined = (
        select(AdminAuditLog, actor, target)
        .outerjoin(actor, actor.id == AdminAuditLog.actor_user_id)
        .outerjoin(target, target.id == AdminAuditLog.target_user_id)
        .where(*filters)
    )
    total = int(
        await session.scalar(
            select(func.count(AdminAuditLog.id))
            .outerjoin(actor, actor.id == AdminAuditLog.actor_user_id)
            .outerjoin(target, target.id == AdminAuditLog.target_user_id)
            .where(*filters)
        )
        or 0
    )
    rows = (
        await session.execute(
            joined.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    actions = list(
        (
            await session.scalars(
                select(AdminAuditLog.action).distinct().order_by(AdminAuditLog.action)
            )
        ).all()
    )
    return AuditLogListRead(
        items=[_serialize(log, actor_user, target_user) for log, actor_user, target_user in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
        available_actions=actions,
    )

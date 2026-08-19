import hashlib
import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.oauth_account import UserOAuthAccount
from app.models.user import User
from app.schemas.oauth import OAuthIdentity
from app.services.auth_service import ensure_user_can_authenticate, get_user_by_email
from app.services.email_outbox import enqueue_welcome_email

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def oauth_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"error": {"code": code, "message": message}}
    )


def normalize_provider(provider: str) -> str:
    return provider.strip().lower()


async def get_by_provider_subject(
    session: AsyncSession,
    provider: str,
    provider_subject: str,
    provider_instance: str | None = None,
) -> UserOAuthAccount | None:
    instance_clause = (
        UserOAuthAccount.provider_instance == provider_instance
        if provider_instance
        else UserOAuthAccount.provider_instance.is_(None)
    )
    return await session.scalar(
        select(UserOAuthAccount).where(
            UserOAuthAccount.provider == normalize_provider(provider),
            UserOAuthAccount.provider_subject == str(provider_subject),
            instance_clause,
        )
    )


async def get_for_user(session: AsyncSession, user_id: object) -> list[UserOAuthAccount]:
    rows = await session.scalars(
        select(UserOAuthAccount)
        .where(UserOAuthAccount.user_id == user_id)
        .order_by(UserOAuthAccount.provider.asc())
    )
    return list(rows)


async def get_for_user_provider(
    session: AsyncSession, user_id: object, provider: str
) -> UserOAuthAccount | None:
    return await session.scalar(
        select(UserOAuthAccount).where(
            UserOAuthAccount.user_id == user_id,
            UserOAuthAccount.provider == normalize_provider(provider),
        )
    )


async def create_oauth_account(
    session: AsyncSession, user: User, identity: OAuthIdentity
) -> UserOAuthAccount:
    account = UserOAuthAccount(
        user_id=user.id,
        provider=normalize_provider(identity.provider),
        provider_instance=identity.provider_instance,
        provider_subject=identity.subject,
        provider_email=str(identity.email) if identity.email else None,
        provider_username=identity.username,
        provider_avatar_url=identity.avatar_url,
        provider_profile_url=identity.profile_url,
        last_login_at=utcnow(),
    )
    session.add(account)
    return account


def update_oauth_account(account: UserOAuthAccount, identity: OAuthIdentity) -> None:
    account.provider_instance = identity.provider_instance
    account.provider_email = str(identity.email) if identity.email else None
    account.provider_username = identity.username
    account.provider_avatar_url = identity.avatar_url
    account.provider_profile_url = identity.profile_url
    account.updated_at = utcnow()


def touch_last_login(account: UserOAuthAccount, user: User) -> None:
    now = utcnow()
    account.last_login_at = now
    account.updated_at = now
    user.last_login_at = now


def verify_matching_provider_email(user: User, identity: OAuthIdentity) -> None:
    if not identity.email_verified or not identity.email:
        return
    if user.email.strip().casefold() == str(identity.email).strip().casefold():
        user.is_verified = True


async def authenticate_oauth_identity(session: AsyncSession, identity: OAuthIdentity) -> User:
    provider = normalize_provider(identity.provider)
    account = await get_by_provider_subject(
        session,
        provider,
        identity.subject,
        identity.provider_instance,
    )
    if account:
        user = await session.get(User, account.user_id)
        if not user:
            raise oauth_error(
                "ACCOUNT_DISABLED", "Dieses Konto ist deaktiviert.", status.HTTP_403_FORBIDDEN
            )
        await ensure_user_can_authenticate(
            session,
            user,
            provider=provider,
            audit_interactive_attempt=True,
        )
        was_verified = user.is_verified
        update_oauth_account(account, identity)
        verify_matching_provider_email(user, identity)
        if not was_verified and user.is_verified:
            enqueue_welcome_email(session, user)
        touch_last_login(account, user)
        session.add(
            AdminAuditLog(
                actor_user_id=user.id,
                target_user_id=user.id,
                action="OAUTH_LOGIN_SUCCESS",
                resource_type="USER",
                resource_id=user.id,
                event_metadata={
                    "provider": provider,
                    "provider_instance": identity.provider_instance,
                },
            )
        )
        await session.commit()
        await session.refresh(user)
        logger.info("OAuth login succeeded for user %s via %s", user.id, provider)
        return user

    if identity.email:
        existing_user = await get_user_by_email(session, str(identity.email))
        if existing_user:
            raise oauth_error(
                "OAUTH_EMAIL_CONFLICT",
                f"Es existiert bereits ein Konto mit dieser E-Mail-Adresse. Bitte melden Sie sich zuerst an und verknüpfen Sie {provider_label(provider)} anschließend im Profil.",
                status.HTTP_409_CONFLICT,
            )

    placeholder_key = hashlib.sha256(
        f"{provider}:{identity.provider_instance or ''}:{identity.subject}".encode()
    ).hexdigest()[:32]
    user = User(
        email=(
            str(identity.email)
            if identity.email
            else f"{provider}-{placeholder_key}@pending.stadtplaner.oklabflensburg.de"
        ),
        email_pending=not bool(identity.email),
        display_name=identity.display_name or identity.username or "",
        is_verified=bool(identity.email and identity.email_verified),
    )
    session.add(user)
    await session.flush()
    await create_oauth_account(session, user, identity)
    if user.is_verified:
        enqueue_welcome_email(session, user)
    user.last_login_at = utcnow()
    session.add(
        AdminAuditLog(
            actor_user_id=user.id,
            target_user_id=user.id,
            action="OAUTH_LOGIN_SUCCESS",
            resource_type="USER",
            resource_id=user.id,
            event_metadata={
                "provider": provider,
                "provider_instance": identity.provider_instance,
                "new_user": True,
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        existing = await get_by_provider_subject(
            session,
            provider,
            identity.subject,
            identity.provider_instance,
        )
        if existing:
            linked_user = await session.get(User, existing.user_id)
            if linked_user:
                await ensure_user_can_authenticate(
                    session,
                    linked_user,
                    provider=provider,
                    audit_interactive_attempt=True,
                )
                was_verified = linked_user.is_verified
                update_oauth_account(existing, identity)
                verify_matching_provider_email(linked_user, identity)
                if not was_verified and linked_user.is_verified:
                    enqueue_welcome_email(session, linked_user)
                touch_last_login(existing, linked_user)
                await session.commit()
                await session.refresh(linked_user)
                return linked_user
        raise oauth_error(
            "OAUTH_LOGIN_FAILED", "OAuth-Anmeldung fehlgeschlagen.", status.HTTP_409_CONFLICT
        ) from exc
    await session.refresh(user)
    logger.info("OAuth user created for user %s via %s", user.id, provider)
    return user


async def link_oauth_account(
    session: AsyncSession, user: User, identity: OAuthIdentity
) -> UserOAuthAccount:
    provider = normalize_provider(identity.provider)
    existing_identity = await get_by_provider_subject(
        session,
        provider,
        identity.subject,
        identity.provider_instance,
    )
    if existing_identity and existing_identity.user_id != user.id:
        raise oauth_error(
            "OAUTH_ACCOUNT_ALREADY_LINKED",
            f"Dieses {provider_label(provider)}-Konto ist bereits mit einem anderen Benutzerkonto verbunden.",
            status.HTTP_409_CONFLICT,
        )
    existing_provider = await get_for_user_provider(session, user.id, provider)
    if existing_provider and (
        not existing_identity or existing_provider.id != existing_identity.id
    ):
        raise oauth_error(
            "OAUTH_ACCOUNT_ALREADY_LINKED",
            f"Ihr Konto ist bereits mit {provider_label(provider)} verbunden.",
            status.HTTP_409_CONFLICT,
        )
    account = existing_identity or await create_oauth_account(session, user, identity)
    was_verified = user.is_verified
    update_oauth_account(account, identity)
    verify_matching_provider_email(user, identity)
    if not was_verified and user.is_verified:
        enqueue_welcome_email(session, user)
    touch_last_login(account, user)
    session.add(
        AdminAuditLog(
            actor_user_id=user.id,
            target_user_id=user.id,
            action="OAUTH_ACCOUNT_LINKED",
            resource_type="USER",
            resource_id=user.id,
            event_metadata={
                "provider": provider,
                "provider_instance": identity.provider_instance,
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise oauth_error(
            "OAUTH_ACCOUNT_ALREADY_LINKED",
            f"Dieses {provider_label(provider)}-Konto ist bereits verbunden.",
            status.HTTP_409_CONFLICT,
        ) from exc
    await session.refresh(account)
    logger.info("OAuth account linked for user %s via %s", user.id, provider)
    return account


async def unlink_oauth_account(session: AsyncSession, user: User, provider: str) -> None:
    normalized = normalize_provider(provider)
    account = await get_for_user_provider(session, user.id, normalized)
    if not account:
        raise oauth_error(
            "OAUTH_ACCOUNT_NOT_LINKED",
            "Dieses externe Konto ist nicht verknüpft.",
            status.HTTP_404_NOT_FOUND,
        )

    other_count = await session.scalar(
        select(func.count(UserOAuthAccount.id)).where(
            UserOAuthAccount.user_id == user.id,
            UserOAuthAccount.provider != normalized,
        )
    )
    has_password = bool(user.password_hash)
    if not has_password and int(other_count or 0) == 0:
        raise oauth_error(
            "LAST_AUTH_METHOD",
            "Diese Verbindung kann nicht entfernt werden, da sie derzeit Ihre einzige Anmeldemethode ist.",
            status.HTTP_409_CONFLICT,
        )

    provider_instance = account.provider_instance
    await session.delete(account)
    session.add(
        AdminAuditLog(
            actor_user_id=user.id,
            target_user_id=user.id,
            action="OAUTH_ACCOUNT_UNLINKED",
            resource_type="USER",
            resource_id=user.id,
            event_metadata={
                "provider": normalized,
                "provider_instance": provider_instance,
            },
        )
    )
    await session.commit()
    logger.info("OAuth account unlinked for user %s via %s", user.id, normalized)


def provider_label(provider: str) -> str:
    return {
        "github": "GitHub",
        "google": "Google",
        "mastodon": "Mastodon",
    }.get(provider, provider.capitalize())

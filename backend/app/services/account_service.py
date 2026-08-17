import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import verify_password
from app.models.admin_audit_log import AdminAuditLog
from app.models.city_metrics import CityMetrics
from app.models.oauth_account import OAuthFlowGrant, UserOAuthAccount
from app.models.password_reset_token import PasswordResetToken
from app.models.social_publication import SocialPublishingSettings
from app.models.user import AccountDeactivationReason, User
from app.models.user_polygon import UserPolygon
from app.models.user_session import UserSession
from app.models.verification_token import EmailVerificationToken


def account_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


async def _lock_user_and_protect_last_superuser(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user:
        raise account_error(
            "AUTH_REQUIRED", "Bitte melde dich erneut an.", status.HTTP_401_UNAUTHORIZED
        )
    if user.is_superuser:
        # Lock all candidates in a stable order so two superusers cannot remove the
        # final two accounts concurrently after both observed a count of two.
        active_ids = list(
            (
                await session.scalars(
                    select(User.id)
                    .where(User.is_superuser.is_(True), User.is_active.is_(True))
                    .order_by(User.id)
                    .with_for_update()
                )
            ).all()
        )
        if len(active_ids) <= 1:
            raise account_error(
                "LAST_SUPERUSER_REQUIRED",
                "Das letzte aktive Superuser-Konto kann nicht deaktiviert oder gelöscht werden. "
                "Übertrage die Superuser-Berechtigung zunächst auf ein anderes Konto.",
                status.HTTP_409_CONFLICT,
            )
    return user


async def deactivate_own_account(session: AsyncSession, user_id: uuid.UUID) -> None:
    user = await _lock_user_and_protect_last_superuser(session, user_id)
    if not user.is_active:
        return
    user.is_active = False
    now = datetime.now(UTC)
    user.deactivated_at = now
    user.deactivation_reason = AccountDeactivationReason.SELF_DEACTIVATED
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revocation_reason="account_deactivated")
    )
    session.add(
        AdminAuditLog(
            actor_user_id=user.id,
            target_user_id=user.id,
            action="ACCOUNT_DEACTIVATED",
            resource_type="USER",
            resource_id=user.id,
            event_metadata={"self_service": True},
        )
    )
    await session.commit()


async def delete_own_account(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    confirmation_text: str,
    current_password: str | None,
    authenticated_at: datetime | None,
    recent_auth_seconds: int,
) -> str | None:
    if confirmation_text.strip().casefold() != "löschen".casefold():
        raise account_error(
            "INVALID_DELETE_CONFIRMATION",
            "Bitte gib zur Bestätigung LÖSCHEN ein.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    user = await _lock_user_and_protect_last_superuser(session, user_id)
    if user.password_hash:
        if not current_password or not verify_password(current_password, user.password_hash):
            raise account_error(
                "INVALID_CURRENT_PASSWORD",
                "Das aktuelle Passwort ist nicht korrekt.",
                status.HTTP_403_FORBIDDEN,
            )
    else:
        now = datetime.now(UTC)
        if not authenticated_at or (now - authenticated_at).total_seconds() > recent_auth_seconds:
            raise account_error(
                "RECENT_AUTH_REQUIRED",
                "Deine Anmeldung ist für diese Aktion zu alt. Bitte melde dich erneut an.",
                status.HTTP_403_FORBIDDEN,
            )

    avatar_url = user.avatar_url
    # Personal/credential data is removed explicitly in one transaction. Public
    # domain data survives; only account creator/updater references are anonymized.
    await session.execute(
        update(UserPolygon)
        .where(UserPolygon.created_by_user_id == user.id)
        .values(created_by_user_id=None)
    )
    await session.execute(
        update(UserPolygon)
        .where(UserPolygon.updated_by_user_id == user.id)
        .values(updated_by_user_id=None)
    )
    await session.execute(
        update(CityMetrics)
        .where(CityMetrics.updated_by_user_id == user.id)
        .values(updated_by_user_id=None)
    )
    await session.execute(
        update(SocialPublishingSettings)
        .where(SocialPublishingSettings.updated_by_user_id == user.id)
        .values(updated_by_user_id=None)
    )
    await session.execute(
        update(AdminAuditLog)
        .where(AdminAuditLog.actor_user_id == user.id)
        .values(actor_user_id=None)
    )
    await session.execute(
        update(AdminAuditLog)
        .where(AdminAuditLog.target_user_id == user.id)
        .values(target_user_id=None)
    )
    for model in (
        OAuthFlowGrant,
        UserOAuthAccount,
        UserSession,
        PasswordResetToken,
        EmailVerificationToken,
    ):
        await session.execute(delete(model).where(model.user_id == user.id))

    session.add(
        AdminAuditLog(
            actor_user_id=None,
            target_user_id=None,
            action="ACCOUNT_DELETED",
            resource_type="USER",
            resource_id=user.id,
            event_metadata={"self_service": True},
        )
    )
    await session.delete(user)
    await session.commit()
    return avatar_url

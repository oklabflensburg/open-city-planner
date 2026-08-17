import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin_audit_log import AdminAuditLog
from app.models.user import AccountDeactivationReason, User
from app.models.user_session import UserSession
from app.schemas.admin import AdminRoleRead, AdminUserRead
from app.services.notification_policy import DomainEvent, NotificationEventType
from app.services.notifications import notify_users, publish_notifications

ROLE_DEFINITIONS: dict[str, str] = {
    "VERWALTUNG": (
        "Zugriff auf interne Eigentümer- und Preisdaten, alle Flächen sowie die zentrale "
        "Kennzahlenverwaltung."
    )
}


def normalize_roles(roles: list[str] | None) -> list[str]:
    return sorted({role.strip().upper() for role in (roles or []) if role.strip()})


def ensure_known_role(role: str) -> str:
    normalized = role.strip().upper()
    if normalized not in ROLE_DEFINITIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "ROLE_NOT_FOUND", "message": "Diese Rolle ist nicht bekannt."}
            },
        )
    return normalized


def role_list() -> list[AdminRoleRead]:
    return [
        AdminRoleRead(name=name, description=description)
        for name, description in ROLE_DEFINITIONS.items()
    ]


def serialize_admin_user(user: User) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_superuser=user.is_superuser,
        roles=normalize_roles(user.roles),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        oauth_providers=sorted(account.provider for account in (user.oauth_accounts or [])),
    )


async def list_users(
    session: AsyncSession,
    *,
    search: str | None,
    page: int,
    page_size: int,
    role: str | None,
    is_active: bool | None,
) -> tuple[list[AdminUserRead], int]:
    filters = []
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        filters.append(
            or_(
                User.email.ilike(pattern),
                User.display_name.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                func.concat(User.first_name, " ", User.last_name).ilike(pattern),
            )
        )
    if role:
        normalized_role = ensure_known_role(role)
        filters.append(cast(User.roles, String).ilike(f'%"{normalized_role}"%'))
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    total = int(await session.scalar(select(func.count(User.id)).where(*filters)) or 0)
    result = await session.scalars(
        select(User)
        .options(selectinload(User.oauth_accounts))
        .where(*filters)
        .order_by(func.lower(func.coalesce(User.display_name, User.email)), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [serialize_admin_user(user) for user in result.all()], total


async def get_admin_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).options(selectinload(User.oauth_accounts)).where(User.id == user_id)
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "USER_NOT_FOUND", "message": "Benutzerkonto nicht gefunden."}
            },
        )
    return user


async def revoke_user_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def assign_role(session: AsyncSession, target: User, role: str, actor: User) -> bool:
    normalized_role = ensure_known_role(role)
    roles = normalize_roles(target.roles)
    if normalized_role in roles:
        return False
    target.roles = [*roles, normalized_role]
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            target_user_id=target.id,
            action="USER_ROLE_ASSIGNED",
            role=normalized_role,
        )
    )
    notifications = await notify_users(
        session,
        [target.id],
        DomainEvent(
            event_type=NotificationEventType.ROLE_ASSIGNED,
            actor_user_id=actor.id,
            resource_type="USER",
            resource_id=str(target.id),
            metadata={"role": normalized_role},
        ),
    )
    await revoke_user_sessions(session, target.id)
    await session.commit()
    publish_notifications(notifications)
    return True


async def remove_role(session: AsyncSession, target: User, role: str, actor: User) -> bool:
    normalized_role = ensure_known_role(role)
    roles = normalize_roles(target.roles)
    if normalized_role not in roles:
        return False
    target.roles = [value for value in roles if value != normalized_role]
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            target_user_id=target.id,
            action="USER_ROLE_REMOVED",
            role=normalized_role,
        )
    )
    notifications = await notify_users(
        session,
        [target.id],
        DomainEvent(
            event_type=NotificationEventType.ROLE_REMOVED,
            actor_user_id=actor.id,
            resource_type="USER",
            resource_id=str(target.id),
            metadata={"role": normalized_role},
        ),
    )
    await revoke_user_sessions(session, target.id)
    await session.commit()
    publish_notifications(notifications)
    return True


async def set_user_active(
    session: AsyncSession, target: User, is_active: bool, actor: User
) -> None:
    if target.id == actor.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CANNOT_DISABLE_SELF",
                    "message": "Das eigene Superuser-Konto kann nicht deaktiviert werden.",
                }
            },
        )
    if target.is_active == is_active:
        return
    if target.is_superuser and not is_active:
        active_superusers = int(
            await session.scalar(
                select(func.count(User.id)).where(
                    User.is_superuser.is_(True), User.is_active.is_(True)
                )
            )
            or 0
        )
        if active_superusers <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "LAST_SUPERUSER_REQUIRED",
                        "message": "Der letzte aktive Superuser darf nicht deaktiviert werden.",
                    }
                },
            )
    target.is_active = is_active
    target.deactivated_at = None if is_active else datetime.now(UTC)
    target.deactivation_reason = None if is_active else AccountDeactivationReason.ADMIN_DEACTIVATED
    session.add(
        AdminAuditLog(
            actor_user_id=actor.id,
            target_user_id=target.id,
            action="USER_ACTIVATED" if is_active else "USER_DEACTIVATED",
        )
    )
    notifications = await notify_users(
        session,
        [target.id],
        DomainEvent(
            event_type=(
                NotificationEventType.ACCOUNT_REACTIVATED
                if is_active
                else NotificationEventType.ACCOUNT_DEACTIVATED
            ),
            actor_user_id=actor.id,
            resource_type="USER",
            resource_id=str(target.id),
        ),
    )
    if not is_active:
        await revoke_user_sessions(session, target.id)
    await session.commit()
    publish_notifications(notifications)

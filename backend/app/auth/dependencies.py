import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import validate_csrf
from app.auth.jwt import decode_jwt
from app.core.config import get_settings
from app.db.session import get_session
from app.models.mfa import UserMfaMethod, UserWebAuthnCredential
from app.models.user import User
from app.services.auth_service import get_user_by_id, inactive_account_error

SessionDep = Annotated[AsyncSession, Depends(get_session)]
access_cookie_scheme = APIKeyCookie(
    name=get_settings().auth_access_cookie_name,
    scheme_name="AccessCookie",
    auto_error=False,
    description="HttpOnly-Zugriffscookie einer Stadtplaner-Sitzung. Schreibzugriffe benötigen zusätzlich den X-CSRF-Token-Header.",
)


def auth_exception(
    code: str = "AUTH_REQUIRED", message: str = "Bitte melden Sie sich an."
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code, "message": message}},
    )


async def get_optional_user(request: Request, session: SessionDep) -> User | None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_access_cookie_name)
    if not token:
        return None
    try:
        payload = decode_jwt(token, "access")
    except jwt.PyJWTError:
        return None
    user = await get_user_by_id(session, payload.get("sub", ""))
    if not user or not user.is_active:
        return None
    return user


async def get_current_user(
    request: Request,
    session: SessionDep,
    _documented_access_cookie: Annotated[str | None, Security(access_cookie_scheme)] = None,
) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.auth_access_cookie_name)
    if not token:
        raise auth_exception("AUTH_REQUIRED", "Bitte melden Sie sich an.")
    try:
        payload = decode_jwt(token, "access")
    except jwt.ExpiredSignatureError as exc:
        raise auth_exception(
            "ACCESS_TOKEN_EXPIRED", "Die Zugriffssitzung muss erneuert werden."
        ) from exc
    except jwt.PyJWTError as exc:
        raise auth_exception("ACCESS_TOKEN_INVALID", "Bitte melden Sie sich erneut an.") from exc
    user = await get_user_by_id(session, payload.get("sub", ""))
    if not user:
        raise auth_exception("AUTH_REQUIRED", "Bitte melden Sie sich erneut an.")
    if not user.is_active:
        raise inactive_account_error(user)
    return user


async def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {"code": "ACCOUNT_INACTIVE", "message": "Dieses Konto ist deaktiviert."}
            },
        )
    return user


async def get_csrf_protected_active_user(
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Active authenticated user for mutations that do not require email verification."""
    validate_csrf(request)
    return user


async def get_verified_user(
    request: Request, user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    validate_csrf(request)
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "EMAIL_NOT_VERIFIED",
                    "message": "Bitte bestätigen Sie zuerst Ihre E-Mail-Adresse.",
                }
            },
        )
    return user


async def require_superuser(
    request: Request,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "SUPERUSER_REQUIRED",
                    "message": "Für die Rollenverwaltung sind Superuser-Rechte erforderlich.",
                }
            },
        )
    settings = get_settings()
    if settings.require_mfa_for_superusers or settings.production:
        totp_method = await session.scalar(
            select(UserMfaMethod.id).where(
                UserMfaMethod.user_id == user.id,
                UserMfaMethod.type == "totp",
                UserMfaMethod.is_enabled.is_(True),
            )
        )
        passkey = await session.scalar(
            select(UserWebAuthnCredential.id).where(UserWebAuthnCredential.user_id == user.id)
        )
        token = request.cookies.get(settings.auth_access_cookie_name)
        try:
            amr = decode_jwt(token or "", "access").get("amr", [])
        except jwt.PyJWTError:
            amr = []
        configured = bool(totp_method or passkey)
        strong_amr = {"otp", "recovery", "webauthn"}
        if not configured:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "MFA_SETUP_REQUIRED",
                        "message": "Für administrative Funktionen ist eine bestätigte Zwei-Faktor-Anmeldung erforderlich.",
                    }
                },
            )
        if not isinstance(amr, list) or not (strong_amr & set(amr)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "MFA_REAUTH_REQUIRED",
                        "message": "Bitte melden Sie sich für administrative Funktionen mit Zwei-Faktor-Authentifizierung erneut an.",
                    }
                },
            )
    return user


async def require_csrf_superuser(
    request: Request,
    user: Annotated[User, Depends(require_superuser)],
) -> User:
    validate_csrf(request)
    return user


def has_role(user: User, role: str) -> bool:
    """Database-backed role check; superusers retain all administrative access."""
    expected = role.strip().upper()
    return user.is_superuser or any(
        value.strip().upper() == expected for value in (user.roles or [])
    )


def can_edit_polygon(user: User, created_by_user_id: uuid.UUID | None) -> bool:
    return has_role(user, "VERWALTUNG") or (
        created_by_user_id is not None and created_by_user_id == user.id
    )


def can_create_polygon(user: User) -> bool:
    return bool(user.is_active)


def can_delete_polygon(user: User, created_by_user_id: uuid.UUID | None) -> bool:
    return has_role(user, "VERWALTUNG") or (
        created_by_user_id is not None and created_by_user_id == user.id
    )


def require_role(role: str) -> Callable[..., User]:
    async def dependency(
        request: Request, user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        validate_csrf(request)
        if not has_role(user, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {"code": "ROLE_REQUIRED", "message": f"Rolle {role} erforderlich."}
                },
            )
        return user

    return dependency


require_verwaltung_user = require_role("VERWALTUNG")

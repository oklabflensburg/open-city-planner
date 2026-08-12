import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import validate_csrf
from app.auth.jwt import decode_jwt
from app.core.config import get_settings
from app.db.session import get_session
from app.models.user import User
from app.services.auth_service import get_user_by_id

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def auth_exception(code: str = "AUTH_REQUIRED", message: str = "Bitte melde dich an.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": {"code": code, "message": message}})


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


async def get_current_user(request: Request, session: SessionDep) -> User:
    user = await get_optional_user(request, session)
    if not user:
        raise auth_exception()
    return user


async def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "ACCOUNT_INACTIVE", "message": "Dieses Konto ist deaktiviert."}})
    return user


async def get_verified_user(request: Request, user: Annotated[User, Depends(get_current_active_user)]) -> User:
    validate_csrf(request)
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "EMAIL_NOT_VERIFIED", "message": "Bitte bestätige zuerst deine E-Mail-Adresse."}})
    return user


def access_cookie() -> str | None:
    settings = get_settings()

    async def dependency(token: str | None = Cookie(default=None, alias=settings.auth_access_cookie_name)) -> str | None:
        return token

    return None


def has_role(user: User, role: str) -> bool:
    """Database-backed role check; superusers retain all administrative access."""
    expected = role.strip().upper()
    return user.is_superuser or any(value.strip().upper() == expected for value in (user.roles or []))


def can_edit_polygon(user: User, created_by_user_id: uuid.UUID | None) -> bool:
    return (
        has_role(user, "VERWALTUNG")
        or (created_by_user_id is not None and created_by_user_id == user.id)
    )


def require_role(role: str) -> Callable[..., User]:
    async def dependency(
        request: Request, user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        validate_csrf(request)
        if not has_role(user, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "ROLE_REQUIRED", "message": f"Rolle {role} erforderlich."}},
            )
        return user

    return dependency


require_verwaltung_user = require_role("VERWALTUNG")

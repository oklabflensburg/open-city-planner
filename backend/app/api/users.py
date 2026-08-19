import uuid
from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy import select

from app.auth.csrf import validate_csrf
from app.auth.dependencies import SessionDep, get_current_active_user
from app.auth.jwt import decode_jwt
from app.core.config import get_settings
from app.models.user import User
from app.models.user_polygon import UserPolygon
from app.schemas.auth import MessageResponse, PasskeyRead, PasskeyRenameRequest
from app.schemas.geojson import PolygonRead
from app.schemas.oauth import UserOAuthAccountRead
from app.schemas.user import AccountDeletionRequest, UserRead, UserUpdate
from app.services.account_service import deactivate_own_account, delete_own_account
from app.services.auth_service import clear_auth_cookies
from app.services.avatar_service import delete_avatar_file, save_avatar
from app.services.email_service import send_mfa_security_email
from app.services.mfa_service import require_recent_auth
from app.services.oauth_account_service import (
    get_for_user,
    normalize_provider,
    unlink_oauth_account,
)
from app.services.passkey_service import list_passkeys, remove_passkey, rename_passkey
from app.services.polygons import serialize_polygon

router = APIRouter(prefix="/users", tags=["Users"])


def _access_authenticated_at(request: Request) -> datetime | None:
    token = request.cookies.get(get_settings().auth_access_cookie_name)
    if not token:
        return None
    try:
        authenticated_at = decode_jwt(token, "access").get("auth_time")
        return datetime.fromtimestamp(int(authenticated_at), UTC)
    except (jwt.PyJWTError, TypeError, ValueError, OverflowError):
        return None


@router.get("/me", response_model=UserRead)
async def get_user_me(user: Annotated[User, Depends(get_current_active_user)]) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def patch_user_me(
    payload: UserUpdate,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    validate_csrf(request)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/me/avatar", response_model=UserRead)
async def post_user_avatar(
    avatar: UploadFile,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    validate_csrf(request)
    old_avatar_url = user.avatar_url
    new_avatar_url = await save_avatar(avatar, user.id)
    user.avatar_url = new_avatar_url
    try:
        await session.commit()
        await session.refresh(user)
    except Exception:
        await session.rollback()
        delete_avatar_file(new_avatar_url)
        raise
    delete_avatar_file(old_avatar_url)
    return UserRead.model_validate(user)


@router.delete("/me/avatar", response_model=UserRead)
async def delete_user_avatar(
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> UserRead:
    validate_csrf(request)
    old_avatar_url = user.avatar_url
    user.avatar_url = None
    await session.commit()
    await session.refresh(user)
    delete_avatar_file(old_avatar_url)
    return UserRead.model_validate(user)


@router.get("/me/oauth-accounts", response_model=list[UserOAuthAccountRead])
async def get_user_oauth_accounts(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_active_user)],
) -> list[UserOAuthAccountRead]:
    return [
        UserOAuthAccountRead.model_validate(account)
        for account in await get_for_user(session, user.id)
    ]


@router.delete("/me/oauth-accounts/{provider}", status_code=204)
async def delete_user_oauth_account(
    provider: str,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    validate_csrf(request)
    require_recent_auth(request)
    await unlink_oauth_account(session, user, normalize_provider(provider))


@router.get("/me/passkeys", response_model=list[PasskeyRead])
async def get_user_passkeys(
    session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]
) -> list[PasskeyRead]:
    return [PasskeyRead.model_validate(value) for value in await list_passkeys(session, user.id)]


@router.patch("/me/passkeys/{credential_id}", response_model=PasskeyRead)
async def patch_user_passkey(
    credential_id: uuid.UUID,
    payload: PasskeyRenameRequest,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> PasskeyRead:
    validate_csrf(request)
    require_recent_auth(request)
    record = await rename_passkey(session, user.id, credential_id, payload.name)
    return PasskeyRead.model_validate(record)


@router.delete("/me/passkeys/{credential_id}", status_code=204)
async def delete_user_passkey(
    credential_id: uuid.UUID,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    validate_csrf(request)
    require_recent_auth(request)
    remaining = await remove_passkey(session, user, credential_id)
    send_mfa_security_email(user, "passkey_removed" if remaining else "passkeys_removed")


@router.get("/me/polygons", response_model=list[PolygonRead])
async def get_my_polygons(
    session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]
) -> list[PolygonRead]:
    rows = await session.scalars(
        select(UserPolygon)
        .where(UserPolygon.created_by_user_id == user.id)
        .order_by(UserPolygon.updated_at.desc())
    )
    return [serialize_polygon(row) for row in rows]


@router.post(
    "/me/deactivate",
    response_model=MessageResponse,
    summary="Eigenes Benutzerkonto deaktivieren",
    responses={
        401: {"description": "Anmeldung erforderlich"},
        409: {"description": "Das letzte aktive Superuser-Konto kann nicht deaktiviert werden"},
    },
)
async def post_deactivate_user_me(
    session: SessionDep,
    response: Response,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> MessageResponse:
    validate_csrf(request)
    await deactivate_own_account(session, user.id)
    clear_auth_cookies(response)
    return MessageResponse(message="Das Konto wurde deaktiviert.")


@router.delete(
    "/me",
    response_model=MessageResponse,
    summary="Eigenes Benutzerkonto dauerhaft löschen",
    responses={
        401: {"description": "Anmeldung erforderlich"},
        403: {"description": "Passwort oder kürzlich erfolgte Anmeldung erforderlich"},
        409: {"description": "Das letzte aktive Superuser-Konto kann nicht gelöscht werden"},
    },
)
async def delete_user_me(
    payload: AccountDeletionRequest,
    session: SessionDep,
    response: Response,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> MessageResponse:
    validate_csrf(request)
    settings = get_settings()
    avatar_url = await delete_own_account(
        session,
        user.id,
        confirmation_text=payload.confirmation_text,
        current_password=payload.current_password,
        authenticated_at=_access_authenticated_at(request),
        recent_auth_seconds=settings.account_deletion_recent_auth_seconds,
    )
    delete_avatar_file(avatar_url)
    clear_auth_cookies(response)
    return MessageResponse(message="Das Konto wurde dauerhaft gelöscht.")

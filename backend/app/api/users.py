from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy import select

from app.auth.csrf import validate_csrf
from app.auth.dependencies import SessionDep, get_current_active_user
from app.models.user import User
from app.models.user_polygon import UserPolygon
from app.schemas.geojson import PolygonRead
from app.schemas.oauth import UserOAuthAccountRead
from app.schemas.user import UserRead, UserUpdate
from app.services.avatar_service import delete_avatar_file, save_avatar
from app.services.oauth_account_service import (
    get_for_user,
    normalize_provider,
    unlink_oauth_account,
)
from app.services.polygons import serialize_polygon

router = APIRouter(prefix="/users", tags=["Users"])


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
    return [UserOAuthAccountRead.model_validate(account) for account in await get_for_user(session, user.id)]


@router.delete("/me/oauth-accounts/{provider}", status_code=204)
async def delete_user_oauth_account(
    provider: str,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    validate_csrf(request)
    await unlink_oauth_account(session, user, normalize_provider(provider))


@router.get("/me/polygons", response_model=list[PolygonRead])
async def get_my_polygons(session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]) -> list[PolygonRead]:
    rows = await session.scalars(
        select(UserPolygon)
        .where(UserPolygon.created_by_user_id == user.id)
        .order_by(UserPolygon.updated_at.desc())
    )
    return [serialize_polygon(row) for row in rows]

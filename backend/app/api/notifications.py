import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.auth.dependencies import (
    SessionDep,
    get_csrf_protected_active_user,
    get_current_active_user,
)
from app.models.notification import NotificationSubscription
from app.models.user import User
from app.schemas.notification import (
    NotificationPage,
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
    NotificationSubscriptionRead,
    NotificationSubscriptionUpdate,
    UnreadCountRead,
)
from app.services.notifications import (
    get_preferences,
    list_notifications,
    mark_all_read,
    mark_read,
    notification_broker,
    remove_subscription,
    unread_count,
    update_preferences,
    upsert_subscription,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationPage)
async def get_notifications(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    category: Annotated[
        str | None, Query(pattern="^(GIS|DATA|OSM|SOCIAL|ACCOUNT|ADMIN|SYSTEM)$")
    ] = None,
    unread_only: bool = False,
) -> NotificationPage:
    return await list_notifications(
        session, user.id, page=page, page_size=page_size, category=category, unread_only=unread_only
    )


@router.get("/unread-count", response_model=UnreadCountRead)
async def get_notification_unread_count(
    session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]
) -> UnreadCountRead:
    return UnreadCountRead(unread_count=await unread_count(session, user.id))


@router.patch("/{notification_id}/read", status_code=204)
async def patch_notification_read(
    notification_id: uuid.UUID,
    session: SessionDep,
    user: Annotated[User, Depends(get_csrf_protected_active_user)],
) -> Response:
    if not await mark_read(session, user.id, notification_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Die Benachrichtigung wurde nicht gefunden.")
    return Response(status_code=204)


@router.post("/read-all", status_code=204)
async def post_notifications_read_all(
    session: SessionDep,
    user: Annotated[User, Depends(get_csrf_protected_active_user)],
) -> Response:
    await mark_all_read(session, user.id)
    return Response(status_code=204)


@router.get("/preferences", response_model=NotificationPreferencesRead)
async def get_notification_preferences(
    session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]
) -> NotificationPreferencesRead:
    preferences = await get_preferences(session, user.id)
    await session.commit()
    return NotificationPreferencesRead.model_validate(preferences)


@router.patch("/preferences", response_model=NotificationPreferencesRead)
async def patch_notification_preferences(
    payload: NotificationPreferencesUpdate,
    session: SessionDep,
    user: Annotated[User, Depends(get_csrf_protected_active_user)],
) -> NotificationPreferencesRead:
    preferences = await update_preferences(session, user.id, payload)
    return NotificationPreferencesRead.model_validate(preferences)


@router.get("/subscriptions", response_model=list[NotificationSubscriptionRead])
async def get_notification_subscriptions(
    session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]
) -> list[NotificationSubscriptionRead]:
    rows = await session.scalars(
        select(NotificationSubscription)
        .where(NotificationSubscription.user_id == user.id)
        .order_by(NotificationSubscription.created_at.desc())
    )
    return [NotificationSubscriptionRead.model_validate(item) for item in rows]


@router.put("/subscriptions", response_model=NotificationSubscriptionRead)
async def put_notification_subscription(
    payload: NotificationSubscriptionUpdate,
    session: SessionDep,
    user: Annotated[User, Depends(get_csrf_protected_active_user)],
) -> NotificationSubscriptionRead:
    item = await upsert_subscription(
        session,
        user_id=user.id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        event_types=payload.event_types,
    )
    return NotificationSubscriptionRead.model_validate(item)


@router.delete("/subscriptions/{resource_type}/{resource_id}", status_code=204)
async def delete_notification_subscription(
    resource_type: str,
    resource_id: str,
    session: SessionDep,
    user: Annotated[User, Depends(get_csrf_protected_active_user)],
) -> Response:
    await remove_subscription(
        session, user_id=user.id, resource_type=resource_type.upper(), resource_id=resource_id
    )
    return Response(status_code=204)


@router.get("/stream", response_class=StreamingResponse)
async def stream_notifications(
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> StreamingResponse:
    async def events():
        yield "retry: 3000\nevent: ready\ndata: {}\n\n"
        async with notification_broker.subscribe(user.id) as queue:
            while not await request.is_disconnected():
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20)
                    yield notification_broker.event_payload(item)
                except TimeoutError:
                    yield ": keep-alive\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )

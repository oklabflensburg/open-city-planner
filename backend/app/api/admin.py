import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.auth.dependencies import (
    SessionDep,
    require_csrf_superuser,
    require_superuser,
)
from app.cache.service import cache_service
from app.models.user import User
from app.schemas.admin import (
    AdminRoleRead,
    AdminUserListRead,
    AdminUserRead,
    AdminUserStatusUpdate,
    AuditLogListRead,
)
from app.services.admin_users import (
    assign_role,
    get_admin_user,
    list_users,
    remove_role,
    role_list,
    serialize_admin_user,
    set_user_active,
)
from app.services.audit_logs import list_audit_logs
from app.services.cache_versions import bump_cache_versions

router = APIRouter(prefix="/admin", tags=["Administration"])
CACHE_NAMESPACES = {"osm", "analytics", "analysis-areas", "polygons"}


@router.get("/cache/stats")
async def get_cache_stats(
    response: Response,
    _actor: Annotated[User, Depends(require_superuser)],
) -> dict:
    private_no_store(response)
    return await cache_service.stats()


@router.post("/cache/invalidate")
async def invalidate_cache(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_csrf_superuser)],
    namespaces: str = Query(default="analytics,analysis-areas,polygons"),
) -> dict:
    private_no_store(response)
    selected = tuple(dict.fromkeys(item.strip() for item in namespaces.split(",") if item.strip()))
    invalid = set(selected) - CACHE_NAMESPACES
    if invalid:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Invalid cache namespace")
    await bump_cache_versions(session, selected)
    await session.commit()
    return {"invalidated": list(selected)}


def private_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get(
    "/audit-logs",
    response_model=AuditLogListRead,
    summary="Auditlog-Einträge auflisten",
    description="Liefert das unveränderliche administrative Auditlog ausschließlich für angemeldete Superuser.",
    responses={
        401: {"description": "Keine gültige Sitzung"},
        403: {"description": "Superuser-Berechtigung erforderlich"},
        422: {"description": "Ungültiger Filter oder Zeitraum"},
    },
)
async def get_audit_logs(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    action: str | None = Query(default=None, max_length=80),
    user_id: uuid.UUID | None = None,
    resource_type: str | None = Query(default=None, pattern="^(USER|SYSTEM)$"),
    resource_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = Query(default=None, max_length=200),
) -> AuditLogListRead:
    private_no_store(response)
    if (date_from and date_from.tzinfo is None) or (date_to and date_to.tzinfo is None):
        raise HTTPException(status_code=422, detail="date_from and date_to must include a timezone")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    return await list_audit_logs(
        session, page=page, page_size=page_size, action=action, user_id=user_id,
        resource_type=resource_type, resource_id=resource_id,
        date_from=date_from, date_to=date_to, search=search,
    )


@router.get("/roles", response_model=list[AdminRoleRead])
async def get_admin_roles(
    response: Response,
    _actor: Annotated[User, Depends(require_superuser)],
) -> list[AdminRoleRead]:
    private_no_store(response)
    return role_list()


@router.get("/users", response_model=AdminUserListRead)
async def get_admin_users(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    role: str | None = Query(default=None, max_length=80),
    is_active: bool | None = Query(default=None),
) -> AdminUserListRead:
    private_no_store(response)
    items, total = await list_users(
        session,
        search=search,
        page=page,
        page_size=page_size,
        role=role,
        is_active=is_active,
    )
    return AdminUserListRead(items=items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserRead)
async def get_admin_user_detail(
    user_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> AdminUserRead:
    private_no_store(response)
    return serialize_admin_user(await get_admin_user(session, user_id))


@router.put("/users/{user_id}/roles/{role}", response_model=AdminUserRead)
async def put_admin_user_role(
    user_id: uuid.UUID,
    role: str,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> AdminUserRead:
    private_no_store(response)
    target = await get_admin_user(session, user_id)
    await assign_role(session, target, role, actor)
    return serialize_admin_user(target)


@router.delete(
    "/users/{user_id}/roles/{role}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_admin_user_role(
    user_id: uuid.UUID,
    role: str,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> None:
    private_no_store(response)
    target = await get_admin_user(session, user_id)
    await remove_role(session, target, role, actor)


@router.patch("/users/{user_id}/status", response_model=AdminUserRead)
async def patch_admin_user_status(
    user_id: uuid.UUID,
    payload: AdminUserStatusUpdate,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> AdminUserRead:
    private_no_store(response)
    target = await get_admin_user(session, user_id)
    await set_user_active(session, target, payload.is_active, actor)
    return serialize_admin_user(target)

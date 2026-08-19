import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.auth.dependencies import (
    SessionDep,
    require_csrf_superuser,
    require_superuser,
)
from app.cache.service import cache_service
from app.core.config import get_settings
from app.models.social_publication import SocialPublicationOutbox
from app.models.user import User
from app.schemas.admin import (
    AdminRoleRead,
    AdminUserListRead,
    AdminUserRead,
    AdminUserStatusUpdate,
    AuditLogListRead,
    EmailTemplateDetailRead,
    EmailTemplateListItemRead,
    EmailTemplatePreviewRead,
    EmailTemplateReset,
    EmailTemplateTestSendRead,
    EmailTemplateUpdate,
)
from app.schemas.social import (
    MastodonAdminStatusRead,
    SocialPublicationApprovalUpdate,
    SocialPublicationApproveAndPublishUpdate,
    SocialPublicationItemRead,
    SocialPublicationListRead,
    SocialPublicationPreviewRead,
    SocialPublishingSettingsRead,
    SocialPublishingSettingsUpdate,
)
from app.services.admin_email_templates import (
    EmailTemplateVersionConflict,
    get_email_template,
    list_email_templates,
    preview_email_template,
    reset_email_template,
    send_test_email,
    update_email_template,
)
from app.services.admin_social import (
    approve_social_publication,
    cancel_social_publication,
    get_social_publication,
    list_social_publications,
    mastodon_admin_status,
    retry_social_publication,
    social_publication_preview,
    social_settings_read,
    update_social_settings,
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
from app.services.email_service import EmailTemplateValidationError
from app.services.rate_limit import check_rate_limit, rate_limit_key
from app.services.social_screenshots import ScreenshotService

router = APIRouter(prefix="/admin", tags=["Administration"])
CACHE_NAMESPACES = {"osm", "analytics", "analysis-areas", "polygons"}


def email_template_error(exc: EmailTemplateValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "error": {
                "code": exc.code,
                "message": str(exc),
                **exc.details,
            }
        },
    )


def email_template_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": {
                "code": "EMAIL_TEMPLATE_VERSION_CONFLICT",
                "message": "Die Vorlage wurde zwischenzeitlich geändert. Bitte laden Sie sie neu.",
            }
        },
    )


@router.get("/email-templates", response_model=list[EmailTemplateListItemRead])
async def get_email_templates_admin(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> list[EmailTemplateListItemRead]:
    private_no_store(response)
    return [EmailTemplateListItemRead.model_validate(item) for item in await list_email_templates(session)]


@router.get("/email-templates/{key}", response_model=EmailTemplateDetailRead)
async def get_email_template_admin(
    key: str,
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> EmailTemplateDetailRead:
    private_no_store(response)
    try:
        return EmailTemplateDetailRead.model_validate(await get_email_template(session, key))
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.patch("/email-templates/{key}", response_model=EmailTemplateDetailRead)
async def patch_email_template_admin(
    key: str,
    payload: EmailTemplateUpdate,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> EmailTemplateDetailRead:
    private_no_store(response)
    try:
        result = await update_email_template(
            session,
            key,
            subject=payload.subject,
            html_body=payload.html_body,
            text_body=payload.text_body,
            expected_version=payload.version,
            actor=actor,
        )
        return EmailTemplateDetailRead.model_validate(result)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EmailTemplateVersionConflict as exc:
        raise email_template_conflict() from exc
    except EmailTemplateValidationError as exc:
        raise email_template_error(exc) from exc


@router.post("/email-templates/{key}/reset", response_model=EmailTemplateDetailRead)
async def reset_email_template_admin(
    key: str,
    payload: EmailTemplateReset,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> EmailTemplateDetailRead:
    private_no_store(response)
    try:
        result = await reset_email_template(
            session, key, expected_version=payload.version, actor=actor
        )
        return EmailTemplateDetailRead.model_validate(result)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EmailTemplateVersionConflict as exc:
        raise email_template_conflict() from exc


@router.post("/email-templates/{key}/preview", response_model=EmailTemplatePreviewRead)
async def preview_email_template_admin(
    key: str,
    payload: EmailTemplateUpdate,
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_csrf_superuser)],
) -> EmailTemplatePreviewRead:
    private_no_store(response)
    try:
        rendered = await preview_email_template(
            session,
            key,
            subject=payload.subject,
            html_body=payload.html_body,
            text_body=payload.text_body,
            version=payload.version,
        )
        return EmailTemplatePreviewRead(
            subject=rendered.subject, html=rendered.html, text=rendered.text
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EmailTemplateValidationError as exc:
        raise email_template_error(exc) from exc


@router.post("/email-templates/{key}/test-send", response_model=EmailTemplateTestSendRead)
async def test_send_email_template_admin(
    key: str,
    payload: EmailTemplateUpdate,
    request: Request,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> EmailTemplateTestSendRead:
    private_no_store(response)
    await check_rate_limit(
        rate_limit_key(request, "admin-email-template-test", str(actor.id)),
        attempts=5,
        window_seconds=600,
    )
    try:
        await send_test_email(
            session,
            key,
            subject=payload.subject,
            html_body=payload.html_body,
            text_body=payload.text_body,
            version=payload.version,
            actor=actor,
        )
        return EmailTemplateTestSendRead(
            message=f"Die Test-E-Mail wurde an {actor.email} gesendet."
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except EmailTemplateValidationError as exc:
        raise email_template_error(exc) from exc


@router.get("/social/mastodon/status", response_model=MastodonAdminStatusRead)
async def get_mastodon_status(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> MastodonAdminStatusRead:
    private_no_store(response)
    return await mastodon_admin_status(session)


@router.get("/social/publications", response_model=SocialPublicationListRead)
async def get_social_publications(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    publication_status: str | None = Query(default=None, alias="status", pattern="^(PENDING_APPROVAL|PENDING|PROCESSING|PUBLISHED|FAILED|CANCELLED|DRY_RUN)$"),
) -> SocialPublicationListRead:
    private_no_store(response)
    return await list_social_publications(session, page=page, page_size=page_size, status=publication_status)


@router.post("/social/publications/{event_id}/retry", response_model=SocialPublicationItemRead)
async def retry_failed_social_publication(
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> SocialPublicationItemRead:
    private_no_store(response)
    try:
        await retry_social_publication(session, event_id, actor)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    item = await get_social_publication(session, event_id)
    if item is None:
        raise HTTPException(404, "Das Veröffentlichungsereignis wurde nicht gefunden.")
    return item


@router.get("/social/settings", response_model=SocialPublishingSettingsRead)
async def get_social_settings_admin(
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> SocialPublishingSettingsRead:
    private_no_store(response)
    return await social_settings_read(session)


@router.patch("/social/settings", response_model=SocialPublishingSettingsRead)
async def patch_social_settings_admin(
    payload: SocialPublishingSettingsUpdate,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> SocialPublishingSettingsRead:
    """Partially update social publishing settings. Superuser only."""
    private_no_store(response)
    try:
        return await update_social_settings(session, payload, actor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get(
    "/social/publications/{event_id}/preview",
    response_model=SocialPublicationPreviewRead,
)
async def get_social_publication_preview(
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> SocialPublicationPreviewRead:
    private_no_store(response)
    try:
        return await social_publication_preview(session, event_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/social/publications/{event_id}/screenshot")
async def get_social_publication_screenshot(
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    _actor: Annotated[User, Depends(require_superuser)],
) -> Response:
    event = await session.get(SocialPublicationOutbox, event_id)
    if event is None or not event.screenshot_path:
        raise HTTPException(404, "Die Screenshot-Vorschau ist noch nicht bereit.")
    try:
        content = ScreenshotService(get_settings()).read(event.screenshot_path)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Die Screenshot-Vorschau ist nicht verfügbar.") from exc
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "Content-Disposition": "inline"},
    )


async def _publication_action_result(
    session: SessionDep,
    event_id: uuid.UUID,
) -> SocialPublicationItemRead:
    item = await get_social_publication(session, event_id)
    if item is None:
        raise HTTPException(404, "Das Veröffentlichungsereignis wurde nicht gefunden.")
    return item


@router.post("/social/publications/{event_id}/approve", response_model=SocialPublicationItemRead)
async def approve_social_publication_admin(
    event_id: uuid.UUID,
    payload: SocialPublicationApprovalUpdate,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> SocialPublicationItemRead:
    private_no_store(response)
    try:
        await approve_social_publication(session, event_id, actor, alt_text=payload.alt_text)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await _publication_action_result(session, event_id)


@router.post(
    "/social/publications/{event_id}/approve-and-publish",
    response_model=SocialPublicationItemRead,
)
async def approve_and_publish_social_publication_admin(
    event_id: uuid.UUID,
    payload: SocialPublicationApproveAndPublishUpdate,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> SocialPublicationItemRead:
    """Approve one publication and enqueue screenshot generation and delivery."""
    private_no_store(response)
    try:
        await approve_social_publication(session, event_id, actor, alt_text=payload.alt_text)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await _publication_action_result(session, event_id)


@router.post("/social/publications/{event_id}/cancel", response_model=SocialPublicationItemRead)
async def cancel_social_publication_admin(
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(require_csrf_superuser)],
) -> SocialPublicationItemRead:
    private_no_store(response)
    try:
        await cancel_social_publication(session, event_id, actor)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await _publication_action_result(session, event_id)


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

        raise HTTPException(status_code=422, detail="Ungültiger Cache-Namensraum.")
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
    resource_type: str | None = Query(default=None, pattern="^(USER|SYSTEM|ANALYSIS_AREA)$"),
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

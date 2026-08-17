import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.integrations.mastodon import MastodonClient, MastodonError
from app.models.admin_audit_log import AdminAuditLog
from app.models.analysis_area import AnalysisArea
from app.models.social_publication import SocialPublicationOutbox, SocialPublishingSettings
from app.models.user import User
from app.models.user_polygon import UserPolygon
from app.schemas.social import (
    MastodonAdminStatusRead,
    SocialEventDefinitionRead,
    SocialPublicationItemRead,
    SocialPublicationListRead,
    SocialPublicationPreviewRead,
    SocialPublishingSettingsRead,
    SocialPublishingSettingsUpdate,
)
from app.services.social_policy import (
    KNOWN_SOCIAL_EVENTS,
    SOCIAL_EVENT_REGISTRY,
    get_social_settings,
)
from app.services.social_publishing import (
    fit_status,
    page_count,
    publication_counts,
    render_event_preview,
)
from app.services.social_screenshots import ScreenshotService, screenshot_target


async def mastodon_admin_status(session: AsyncSession, *, settings: Settings | None = None, client: MastodonClient | None = None) -> MastodonAdminStatusRead:
    settings = settings or get_settings()
    policy = await get_social_settings(session, settings, create=False)
    counts = await publication_counts(session)
    last_publication_at = await session.scalar(select(func.max(SocialPublicationOutbox.published_at)))
    reachable: bool | None = None
    verification_error = None
    if settings.mastodon_access_token:
        mastodon = client or MastodonClient(settings.mastodon_base_url, settings.mastodon_access_token, timeout=settings.mastodon_timeout_seconds)
        try:
            await mastodon.verify_credentials()
            reachable = True
        except MastodonError as exc:
            reachable = False
            verification_error = "Zugangsdaten konnten nicht verifiziert werden." if exc.status_code else "Mastodon ist derzeit nicht erreichbar."
    return MastodonAdminStatusRead(
        enabled=settings.mastodon_enabled and policy.enabled,
        configured=bool(settings.mastodon_access_token),
        reachable=reachable,
        account=settings.mastodon_account_handle,
        account_url=settings.mastodon_account_url,
        area_updates_enabled=settings.mastodon_enabled and policy.enabled,
        dry_run=settings.mastodon_dry_run or policy.approval_mode == "DRY_RUN",
        visibility=policy.default_visibility,
        pending=counts.get("PENDING", 0) + counts.get("PENDING_APPROVAL", 0) + counts.get("PROCESSING", 0),
        failed=counts.get("FAILED", 0),
        published=counts.get("PUBLISHED", 0) + counts.get("DRY_RUN", 0),
        last_publication_at=last_publication_at,
        verification_error=verification_error,
        approval_mode=policy.approval_mode,
    )


def _serialize(event: SocialPublicationOutbox, name: str | None, slug: str | None) -> SocialPublicationItemRead:
    snapshot = event.payload.get("public_snapshot", {})
    return SocialPublicationItemRead(
        id=event.id, created_at=event.created_at, event_type=event.event_type,
        resource_type=event.resource_type, resource_id=event.resource_id,
        resource_name=name or snapshot.get("title") or "Alle Gebiete", resource_slug=slug or snapshot.get("slug"),
        status=event.status, attempt_count=event.attempt_count,
        next_attempt_at=event.next_attempt_at, published_at=event.published_at,
        last_error=event.last_error, remote_url=event.mastodon_status_url,
        changed_fields=list(event.payload.get("changed_fields", [])), dry_run=event.dry_run,
        screenshot_ready=bool(event.screenshot_path or event.mastodon_media_id),
        screenshot_target_url=event.screenshot_target_url,
        screenshot_alt_text=event.screenshot_alt_text,
    )


async def list_social_publications(session: AsyncSession, *, page: int, page_size: int, status: str | None = None) -> SocialPublicationListRead:
    filters = [SocialPublicationOutbox.status == status] if status else []
    total = int(await session.scalar(select(func.count(SocialPublicationOutbox.id)).where(*filters)) or 0)
    rows = (await session.execute(
        select(
            SocialPublicationOutbox,
            func.coalesce(AnalysisArea.name, UserPolygon.name),
            func.coalesce(AnalysisArea.slug, UserPolygon.slug),
        )
        .outerjoin(AnalysisArea, and_(
            SocialPublicationOutbox.resource_type == "ANALYSIS_AREA",
            AnalysisArea.uuid == SocialPublicationOutbox.resource_id,
        ))
        .outerjoin(UserPolygon, and_(
            SocialPublicationOutbox.resource_type == "USER_POLYGON",
            UserPolygon.uuid == SocialPublicationOutbox.resource_id,
        ))
        .where(*filters)
        .order_by(SocialPublicationOutbox.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()
    return SocialPublicationListRead(
        items=[_serialize(event, name, slug) for event, name, slug in rows],
        total=total, page=page, page_size=page_size, pages=page_count(total, page_size),
    )


async def get_social_publication(session: AsyncSession, event_id: uuid.UUID) -> SocialPublicationItemRead | None:
    row = (await session.execute(
        select(
            SocialPublicationOutbox,
            func.coalesce(AnalysisArea.name, UserPolygon.name),
            func.coalesce(AnalysisArea.slug, UserPolygon.slug),
        )
        .outerjoin(AnalysisArea, and_(
            SocialPublicationOutbox.resource_type == "ANALYSIS_AREA",
            AnalysisArea.uuid == SocialPublicationOutbox.resource_id,
        ))
        .outerjoin(UserPolygon, and_(
            SocialPublicationOutbox.resource_type == "USER_POLYGON",
            UserPolygon.uuid == SocialPublicationOutbox.resource_id,
        ))
        .where(SocialPublicationOutbox.id == event_id)
    )).one_or_none()
    return _serialize(*row) if row else None


async def retry_social_publication(session: AsyncSession, event_id: uuid.UUID, actor: User) -> None:
    event = await session.get(SocialPublicationOutbox, event_id, with_for_update=True)
    if event is None:
        raise LookupError("Publication event not found")
    if event.status != "FAILED":
        raise ValueError("Only failed publication events can be retried")
    event.status = "PENDING"
    event.attempt_count = 0
    event.next_attempt_at = datetime.now(UTC)
    event.processing_started_at = None
    event.last_error = None
    session.add(AdminAuditLog(
        actor_user_id=actor.id, action="MASTODON_PUBLICATION_RETRY_REQUESTED",
        resource_type=event.resource_type, resource_id=event.resource_id,
        event_metadata={"event_type": event.event_type, "publication_event_id": str(event.id)},
    ))
    await session.commit()


def _settings_dto(model: SocialPublishingSettings) -> SocialPublishingSettingsRead:
    return SocialPublishingSettingsRead(
        enabled=model.enabled,
        approval_mode=model.approval_mode,
        default_visibility=model.default_visibility,
        language=model.language,
        debounce_seconds=model.debounce_seconds,
        default_hashtags=list(model.default_hashtags or []),
        enabled_events=list(model.enabled_events or []),
        screenshot_viewport=model.screenshot_viewport,
        screenshot_show_map=model.screenshot_show_map,
        screenshot_show_facts=model.screenshot_show_facts,
        screenshot_show_pois=model.screenshot_show_pois,
        screenshot_show_branding=model.screenshot_show_branding,
        polygon_osm_adoption_link_target=getattr(
            model, "polygon_osm_adoption_link_target", "DETAIL_PAGE"
        ),
        registry=[SocialEventDefinitionRead(**definition.__dict__) for definition in SOCIAL_EVENT_REGISTRY],
        updated_at=model.updated_at or datetime.now(UTC),
    )


async def social_settings_read(session: AsyncSession) -> SocialPublishingSettingsRead:
    return _settings_dto(await get_social_settings(session, get_settings()))


async def update_social_settings(
    session: AsyncSession,
    payload: SocialPublishingSettingsUpdate,
    actor: User,
) -> SocialPublishingSettingsRead:
    values = payload.model_dump(exclude_unset=True)
    unknown = set(values.get("enabled_events", [])) - KNOWN_SOCIAL_EVENTS
    if unknown:
        raise ValueError(f"Unknown social publication events: {', '.join(sorted(unknown))}")
    model = await get_social_settings(session, get_settings())
    fields = tuple(values)
    before = {field: getattr(model, field) for field in fields}
    for field, value in values.items():
        setattr(model, field, value)
    model.updated_by_user_id = actor.id
    after = {field: getattr(model, field) for field in fields}
    changed = sorted(field for field in fields if before[field] != after[field])
    if changed:
        session.add(AdminAuditLog(
            actor_user_id=actor.id,
            action="SOCIAL_PUBLISHING_SETTINGS_UPDATED",
            resource_type="SYSTEM",
            event_metadata={
                "changed_fields": changed,
                "before": {field: before[field] for field in changed},
                "after": {field: after[field] for field in changed},
            },
        ))
    await session.commit()
    await session.refresh(model)
    return _settings_dto(model)


async def social_publication_preview(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> SocialPublicationPreviewRead:
    event = await session.get(SocialPublicationOutbox, event_id)
    if event is None:
        raise LookupError("Publication event not found")
    env = get_settings()
    policy = await get_social_settings(session, env, create=False)
    text, resource = await render_event_preview(
        session,
        event,
        env,
        list(policy.default_hashtags or []),
    )
    target = screenshot_target(event, resource, env, policy)
    return SocialPublicationPreviewRead(
        id=event.id,
        text=fit_status(text, 500),
        target_url=target.url,
        target_label=(
            "GIS-Anwendung"
            if event.resource_type == "USER_POLYGON"
            and policy.polygon_osm_adoption_link_target == "GIS"
            else "Flächendetailseite"
            if event.resource_type == "USER_POLYGON"
            else "Öffentliche Gebietsseite"
        ),
        event_type=event.event_type,
        resource_name=resource.name if resource else "Alle Gebiete",
        hashtags=list(policy.default_hashtags or []),
        screenshot_ready=bool(event.screenshot_path),
        screenshot_url=f"/api/v1/admin/social/publications/{event.id}/screenshot" if event.screenshot_path else None,
        alt_text=event.screenshot_alt_text or target.alt_text,
    )


async def approve_social_publication(
    session: AsyncSession,
    event_id: uuid.UUID,
    actor: User,
    *,
    alt_text: str,
) -> None:
    event = await session.get(SocialPublicationOutbox, event_id, with_for_update=True)
    if event is None:
        raise LookupError("Publication event not found")
    if event.status != "PENDING_APPROVAL":
        raise ValueError("Only publications awaiting approval can be approved")
    if not event.screenshot_path:
        raise ValueError("Screenshot preview is not ready")
    previous_alt_text = event.screenshot_alt_text
    event.screenshot_alt_text = alt_text
    event.payload = {**event.payload, "approval_required": False}
    event.status = "PENDING"
    event.next_attempt_at = datetime.now(UTC)
    session.add(AdminAuditLog(
        actor_user_id=actor.id,
        action="MASTODON_PUBLICATION_APPROVED",
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        event_metadata={
            "event_type": event.event_type,
            "publication_event_id": str(event.id),
            "alt_text_changed": previous_alt_text != alt_text,
        },
    ))
    await session.commit()


async def cancel_social_publication(
    session: AsyncSession,
    event_id: uuid.UUID,
    actor: User,
) -> None:
    event = await session.get(SocialPublicationOutbox, event_id, with_for_update=True)
    if event is None:
        raise LookupError("Publication event not found")
    if event.status not in {"PENDING_APPROVAL", "PENDING", "FAILED"}:
        raise ValueError("Publication can no longer be cancelled")
    event.status = "CANCELLED"
    ScreenshotService(get_settings()).remove(event.screenshot_path)
    event.screenshot_path = None
    session.add(AdminAuditLog(
        actor_user_id=actor.id,
        action="MASTODON_PUBLICATION_CANCELLED",
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        event_metadata={"event_type": event.event_type, "publication_event_id": str(event.id)},
    ))
    await session.commit()

import hashlib
import math
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.integrations.mastodon import MastodonClient, MastodonError
from app.models.admin_audit_log import AdminAuditLog
from app.models.analysis_area import AnalysisArea
from app.models.social_publication import SocialPublication, SocialPublicationOutbox
from app.models.user_polygon import UserPolygon
from app.schemas.social import PublicAdoptedPolygonSnapshot
from app.services.social_policy import enabled_event_types, event_is_enabled, get_social_settings
from app.services.social_screenshots import (
    ScreenshotError,
    ScreenshotService,
    screenshot_target,
)

PUBLISHABLE_AREA_TYPES = {"MUNICIPALITY", "DISTRICT", "QUARTER"}
PUBLISHABLE_AREA_FIELDS = frozenset({
    "name", "area_type", "parent_id", "geometry", "area_m2", "source", "statistics",
})
AREA_EVENTS = {"AREA_CREATED", "AREA_PUBLIC_DATA_UPDATED", "AREA_BOUNDARY_UPDATED", "AREA_STATISTICS_UPDATED"}
RETRY_DELAYS = (60, 300, 900, 3600)
COLLECTION_RESOURCE_ID = uuid.UUID(int=0)
POLYGON_ADOPTION_EVENT = "POLYGON_ADOPTED_FROM_OSM"
POLYGON_ADOPTION_DELAY_SECONDS = 30
POLYGON_CATEGORY_LABELS = {
    "warehouse": "Warenhaus", "fashion": "Mode / Bekleidung",
    "food": "Nahrungsmittel / Drogerie", "electronics": "Elektro / Technik",
    "furniture": "Einrichtungsbedarf", "garden": "Garten / Freizeit",
    "other": "Sonstige Waren", "gastronomy": "Gastronomie",
    "services": "Einzelhandelsnahe Dienstleister", "otherAreas": "Sonstige Flächen",
}


class PublicationResourceGone(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_label(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[@#<>]", "", value)).strip()[:160] or "Gebiet"


def canonical_area_url(settings: Settings, slug: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/gebiete/{slug}"


def canonical_polygon_url(
    settings: Settings,
    polygon: UserPolygon,
    link_target: str,
) -> str:
    base = settings.app_base_url.rstrip("/")
    if link_target == "GIS":
        return f"{base}/?polygon={polygon.uuid}"
    return f"{base}/flaechen/{polygon.slug}"


def public_adopted_polygon_snapshot(
    polygon: UserPolygon,
    *,
    osm_type: str,
    osm_id: int,
) -> PublicAdoptedPolygonSnapshot:
    size = polygon.properties.get("size") if polygon.properties else None
    return PublicAdoptedPolygonSnapshot(
        polygon_id=polygon.uuid,
        slug=polygon.slug,
        title=polygon.name,
        category=polygon.category,
        floor=polygon.floor,
        area_size=size if size in {"S", "M", "L", "XL"} else None,
        address=polygon.address_display_name,
        occupancy_status=polygon.occupancy_status or "UNKNOWN",
        osm_type=osm_type,
        osm_id=osm_id,
    )


def render_polygon_adoption_post(
    snapshot: PublicAdoptedPolygonSnapshot,
    polygon: UserPolygon,
    settings: Settings,
    link_target: str,
    hashtags: list[str] | None = None,
) -> str:
    title = _safe_label(snapshot.title)
    detail_parts = [f"Branche: {POLYGON_CATEGORY_LABELS.get(snapshot.category, _safe_label(snapshot.category))}"]
    if snapshot.floor:
        detail_parts.append(f"Etage: {snapshot.floor}")
    if snapshot.area_size:
        detail_parts.append(f"Größe: {snapshot.area_size}")
    if snapshot.address:
        detail_parts.insert(0, _safe_label(snapshot.address))
    tags = list(hashtags or settings.mastodon_hashtag_list)
    normalized = {tag.casefold() for tag in tags}
    if not normalized.intersection({"osm", "openstreetmap"}):
        tags.append("OpenStreetMap")
    hashtag_text = " ".join(f"#{tag}" for tag in tags[:5])
    return (
        "🗺️ Neue Fläche im Stadtplaner\n\n"
        f"„{title}“ wurde aus OpenStreetMap in den Stadtplaner übernommen.\n\n"
        f"{' · '.join(detail_parts)}\n\n"
        "Die Fläche kann nun zusammen mit weiteren offenen Stadt- und Standortdaten analysiert werden.\n\n"
        f"{canonical_polygon_url(settings, polygon, link_target)}\n\n"
        f"{hashtag_text}"
    ).strip()


def render_area_post(
    area: AnalysisArea,
    event_type: str,
    changed_fields: set[str],
    settings: Settings,
    hashtags: list[str] | None = None,
) -> str:
    name = _safe_label(area.name)
    type_label = {"MUNICIPALITY": "Gemeinde", "DISTRICT": "Stadtteil", "QUARTER": "Quartier"}.get(area.area_type, "Gebiet")
    if event_type == "AREA_CREATED":
        heading = f"🏙️ Neue Gebietsseite im Stadtplaner: {name}"
        detail = f"Die öffentliche Seite für das {type_label.lower()} {name} ist jetzt verfügbar."
    elif event_type == "AREA_BOUNDARY_UPDATED" or "geometry" in changed_fields:
        heading = f"🗺️ Gebietsgrenze für {name} aktualisiert"
        detail = f"Die öffentliche Abgrenzung des {type_label.lower()}s wurde im Stadtplaner aktualisiert."
    elif event_type == "AREA_STATISTICS_UPDATED" or "statistics" in changed_fields:
        heading = f"📊 Neue öffentliche Daten für {name}"
        detail = "Die kommunalen Statistik- und Gebietsdaten wurden aktualisiert."
    else:
        heading = f"📍 Gebietsdaten für {name} aktualisiert"
        labels = {
            "name": "Bezeichnung", "area_m2": "Flächengröße", "source": "Datenquelle",
            "source_updated_at": "Datenstand", "parent_id": "Gebietshierarchie",
        }
        visible = [labels[field] for field in sorted(changed_fields) if field in labels]
        detail = "Aktualisiert wurden: " + (", ".join(visible) if visible else "öffentliche Gebietsinformationen") + "."
    hashtag_text = " ".join(f"#{tag}" for tag in (hashtags or settings.mastodon_hashtag_list)[:5])
    return f"{heading}\n\n{detail}\n\n{canonical_area_url(settings, area.slug)}\n\n{hashtag_text}".strip()


def render_statistics_summary_post(settings: Settings, hashtags: list[str] | None = None) -> str:
    hashtag_text = " ".join(f"#{tag}" for tag in (hashtags or settings.mastodon_hashtag_list)[:5])
    return (
        "📊 Kommunale Statistikdaten aktualisiert\n\n"
        "Die öffentlichen Statistikdaten für die Flensburger Gebiete wurden im Stadtplaner aktualisiert.\n\n"
        f"{settings.app_base_url.rstrip('/')}/gebiete\n\n{hashtag_text}"
    ).strip()


def fit_status(text: str, max_characters: int) -> str:
    if len(text) <= max_characters:
        return text
    parts = text.split("\n\n")
    if len(parts) >= 3:
        compact = f"{parts[0]}\n\n{parts[-2]}\n\n{parts[-1]}"
        if len(compact) <= max_characters:
            return compact
    return text[: max(1, max_characters - 1)].rstrip() + "…"


def mastodon_idempotency_key(event_id: uuid.UUID) -> str:
    return hashlib.sha256(str(event_id).encode()).hexdigest()


async def enqueue_area_publication(session: AsyncSession, area: AnalysisArea, event_type: str, changed_fields: set[str], *, settings: Settings | None = None) -> SocialPublicationOutbox | None:
    settings = settings or get_settings()
    allowed = changed_fields & PUBLISHABLE_AREA_FIELDS
    if not settings.mastodon_enabled or area.area_type not in PUBLISHABLE_AREA_TYPES or event_type not in AREA_EVENTS or not allowed:
        return None
    policy = await get_social_settings(session, settings, create=False)
    if not policy.enabled or not event_is_enabled(policy, event_type):
        return None
    pending = await session.scalar(
        select(SocialPublicationOutbox).where(
            SocialPublicationOutbox.platform == "MASTODON",
            SocialPublicationOutbox.resource_type == "ANALYSIS_AREA",
            SocialPublicationOutbox.resource_id == area.uuid,
            SocialPublicationOutbox.status.in_(("PENDING", "PENDING_APPROVAL")),
        ).with_for_update()
    )
    due = _now() + timedelta(seconds=policy.debounce_seconds)
    if pending:
        fields = set(pending.payload.get("changed_fields", [])) | allowed
        pending.payload = {**pending.payload, "changed_fields": sorted(fields)}
        if event_type == "AREA_CREATED" or pending.event_type != "AREA_CREATED" and event_type == "AREA_BOUNDARY_UPDATED":
            pending.event_type = event_type
        pending.next_attempt_at = due
        return pending
    event = SocialPublicationOutbox(
        event_type=event_type, resource_type="ANALYSIS_AREA", resource_id=area.uuid,
        payload={"changed_fields": sorted(allowed), "approval_required": policy.approval_mode == "MANUAL"},
        status="PENDING_APPROVAL" if policy.approval_mode == "MANUAL" else "PENDING",
        next_attempt_at=due,
    )
    session.add(event)
    return event


async def enqueue_statistics_summary(session: AsyncSession, changed_rows: int, *, settings: Settings | None = None) -> SocialPublicationOutbox | None:
    settings = settings or get_settings()
    if not settings.mastodon_enabled or changed_rows <= 0:
        return None
    policy = await get_social_settings(session, settings, create=False)
    if not policy.enabled or not event_is_enabled(policy, "AREA_STATISTICS_BULK_UPDATED"):
        return None
    pending = await session.scalar(select(SocialPublicationOutbox).where(
        SocialPublicationOutbox.platform == "MASTODON",
        SocialPublicationOutbox.resource_type == "ANALYSIS_AREA_COLLECTION",
        SocialPublicationOutbox.resource_id == COLLECTION_RESOURCE_ID,
        SocialPublicationOutbox.status.in_(("PENDING", "PENDING_APPROVAL")),
    ).with_for_update())
    due = _now() + timedelta(seconds=policy.debounce_seconds)
    if pending:
        pending.payload = {
            **pending.payload,
            "changed_rows": int(pending.payload.get("changed_rows", 0)) + changed_rows,
        }
        pending.next_attempt_at = due
        return pending
    event = SocialPublicationOutbox(
        event_type="AREA_STATISTICS_BULK_UPDATED", resource_type="ANALYSIS_AREA_COLLECTION",
        resource_id=COLLECTION_RESOURCE_ID,
        payload={"changed_rows": changed_rows, "approval_required": policy.approval_mode == "MANUAL"},
        status="PENDING_APPROVAL" if policy.approval_mode == "MANUAL" else "PENDING",
        next_attempt_at=due,
    )
    session.add(event)
    return event


async def enqueue_polygon_adoption(
    session: AsyncSession,
    polygon: UserPolygon,
    *,
    osm_type: str,
    osm_id: int,
    settings: Settings | None = None,
) -> SocialPublicationOutbox | None:
    """Enqueue exactly once in the same transaction as a deliberate OSM adoption."""
    settings = settings or get_settings()
    if not settings.mastodon_enabled:
        return None
    policy = await get_social_settings(session, settings, create=False)
    if not policy.enabled or not event_is_enabled(policy, POLYGON_ADOPTION_EVENT):
        return None
    existing = await session.scalar(select(SocialPublicationOutbox).where(
        SocialPublicationOutbox.event_type == POLYGON_ADOPTION_EVENT,
        SocialPublicationOutbox.resource_id == polygon.uuid,
    ))
    if existing is not None:
        return existing
    snapshot = public_adopted_polygon_snapshot(
        polygon, osm_type=osm_type, osm_id=osm_id,
    )
    event = SocialPublicationOutbox(
        event_type=POLYGON_ADOPTION_EVENT,
        resource_type="USER_POLYGON",
        resource_id=polygon.uuid,
        payload={
            "public_snapshot": snapshot.model_dump(mode="json"),
            "source_osm_type": osm_type,
            "source_osm_id": osm_id,
            "approval_required": policy.approval_mode == "MANUAL",
        },
        status="PENDING_APPROVAL" if policy.approval_mode == "MANUAL" else "PENDING",
        next_attempt_at=_now() + timedelta(seconds=POLYGON_ADOPTION_DELAY_SECONDS),
    )
    session.add(event)
    return event


async def cancel_pending_polygon_publications(
    session: AsyncSession,
    polygon_id: uuid.UUID,
) -> int:
    rows = (await session.scalars(select(SocialPublicationOutbox).where(
        SocialPublicationOutbox.resource_type == "USER_POLYGON",
        SocialPublicationOutbox.resource_id == polygon_id,
        SocialPublicationOutbox.status.in_(("PENDING_APPROVAL", "PENDING", "PROCESSING", "FAILED")),
    ).with_for_update())).all()
    screenshots = ScreenshotService(get_settings())
    for event in rows:
        screenshots.remove(event.screenshot_path)
        event.screenshot_path = None
        event.processing_started_at = None
        event.status = "CANCELLED"
        event.last_error = "Die zu veröffentlichende Fläche wurde gelöscht."
        session.add(_audit(event, "MASTODON_PUBLICATION_CANCELLED"))
    return len(rows)


async def _event_context(
    session: AsyncSession,
    event: SocialPublicationOutbox,
    settings: Settings,
    hashtags: list[str],
) -> tuple[str, AnalysisArea | UserPolygon | None]:
    if event.resource_type == "ANALYSIS_AREA_COLLECTION":
        return render_statistics_summary_post(settings, hashtags), None
    if event.resource_type == "USER_POLYGON" and event.event_type == POLYGON_ADOPTION_EVENT:
        polygon = await session.scalar(select(UserPolygon).where(UserPolygon.uuid == event.resource_id))
        if polygon is None:
            raise PublicationResourceGone("Die zu veröffentlichende Fläche wurde gelöscht.")
        try:
            snapshot = public_adopted_polygon_snapshot(
                polygon,
                osm_type=str(event.payload["source_osm_type"]),
                osm_id=int(event.payload["source_osm_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MastodonError(
                "Das öffentliche Polygon-Payload ist ungültig.", retryable=False
            ) from exc
        event.payload = {
            **event.payload,
            "public_snapshot": snapshot.model_dump(mode="json"),
        }
        policy = await get_social_settings(session, settings, create=False)
        return (
            render_polygon_adoption_post(
                snapshot, polygon, settings,
                policy.polygon_osm_adoption_link_target,
                hashtags,
            ),
            polygon,
        )
    area = await session.scalar(select(AnalysisArea).where(AnalysisArea.uuid == event.resource_id))
    if area is None:
        raise PublicationResourceGone("Das zu veröffentlichende Gebiet wurde gelöscht.")
    return (
        render_area_post(
            area,
            event.event_type,
            set(event.payload.get("changed_fields", [])),
            settings,
            hashtags,
        ),
        area,
    )


async def render_event_preview(
    session: AsyncSession,
    event: SocialPublicationOutbox,
    settings: Settings,
    hashtags: list[str],
) -> tuple[str, AnalysisArea | UserPolygon | None]:
    return await _event_context(session, event, settings, hashtags)


def _audit(event: SocialPublicationOutbox, action: str) -> AdminAuditLog:
    metadata: dict[str, str | None] = {
        "event_type": event.event_type,
        "mastodon_status_url": event.mastodon_status_url,
    }
    if event.resource_type == "ANALYSIS_AREA" and event.resource_id:
        metadata["area_id"] = str(event.resource_id)
    elif event.resource_type == "USER_POLYGON" and event.resource_id:
        metadata["polygon_id"] = str(event.resource_id)
    return AdminAuditLog(
        action=action,
        resource_type=(
            "ANALYSIS_AREA" if event.resource_type == "ANALYSIS_AREA"
            else "POLYGON" if event.resource_type == "USER_POLYGON" else "SYSTEM"
        ),
        resource_id=event.resource_id if event.resource_type in {"ANALYSIS_AREA", "USER_POLYGON"} else None,
        event_metadata=metadata,
    )


async def publish_due_events(
    session: AsyncSession,
    *,
    limit: int = 20,
    client: MastodonClient | None = None,
    screenshot_service: ScreenshotService | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    settings = settings or get_settings()
    result = {
        "processed": 0,
        "published": 0,
        "retried": 0,
        "failed": 0,
        "dry_run": 0,
        "prepared": 0,
        "cancelled": 0,
    }
    if not settings.mastodon_enabled:
        return result
    policy = await get_social_settings(session, settings)
    if not policy.enabled:
        return result
    stale = _now() - timedelta(minutes=15)
    stale_rows = (await session.scalars(select(SocialPublicationOutbox).where(
        SocialPublicationOutbox.status == "PROCESSING",
        SocialPublicationOutbox.processing_started_at < stale,
    ))).all()
    for row in stale_rows:
        row.status = "PENDING_APPROVAL" if row.payload.get("approval_required") else "PENDING"
        row.processing_started_at = None
        row.next_attempt_at = _now()
    await session.commit()
    mastodon = client or MastodonClient(
        settings.mastodon_base_url,
        settings.mastodon_access_token or "",
        timeout=settings.mastodon_timeout_seconds,
    )
    screenshots = screenshot_service or ScreenshotService(settings)
    dry_run = settings.mastodon_dry_run or policy.approval_mode == "DRY_RUN"
    max_characters: int | None = 500 if dry_run else None
    max_alt_characters: int | None = 1500 if dry_run else None
    for _ in range(limit):
        event = await session.scalar(
            select(SocialPublicationOutbox).where(
                SocialPublicationOutbox.event_type.in_(enabled_event_types(policy)),
                SocialPublicationOutbox.next_attempt_at <= _now(),
                or_(
                    SocialPublicationOutbox.status == "PENDING",
                    and_(
                        SocialPublicationOutbox.status == "PENDING_APPROVAL",
                        SocialPublicationOutbox.screenshot_path.is_(None),
                    ),
                ),
            )
            .order_by(SocialPublicationOutbox.next_attempt_at, SocialPublicationOutbox.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if event is None:
            break
        approval_required = bool(event.payload.get("approval_required"))
        event.status = "PROCESSING"
        event.processing_started_at = _now()
        event.attempt_count += 1
        await session.commit()
        result["processed"] += 1
        try:
            if max_characters is None:
                max_characters = await mastodon.max_characters()
            text, resource = await _event_context(
                session,
                event,
                settings,
                list(policy.default_hashtags or []),
            )
            text = fit_status(text, max_characters)
            event.content_hash = hashlib.sha256(text.encode()).hexdigest()
            target = screenshot_target(event, resource, settings, policy)
            event.screenshot_target_url = target.url
            event.screenshot_alt_text = target.alt_text
            if not event.screenshot_path:
                event.screenshot_path = await screenshots.capture(
                    event.id,
                    target.url,
                    policy.screenshot_viewport,
                )
                event.screenshot_created_at = _now()
            if approval_required:
                event.status = "PENDING_APPROVAL"
                event.processing_started_at = None
                event.last_error = None
                result["prepared"] += 1
                await session.commit()
                continue
            duplicate = await session.scalar(select(SocialPublication).where(
                SocialPublication.content_hash == event.content_hash,
                SocialPublication.resource_id == event.resource_id,
                SocialPublication.event_type == event.event_type,
            ))
            if duplicate:
                event.status = "PUBLISHED"
                event.published_at = duplicate.published_at
                event.mastodon_status_id = duplicate.remote_id
                event.mastodon_status_url = duplicate.remote_url
                event.mastodon_media_id = duplicate.remote_media_id
                result["published"] += 1
            elif dry_run:
                event.status = "DRY_RUN"
                event.dry_run = True
                event.published_at = _now()
                session.add(SocialPublication(
                    outbox_event_id=event.id,
                    platform=event.platform,
                    event_type=event.event_type,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    content_hash=event.content_hash,
                    dry_run=True,
                    published_at=event.published_at,
                ))
                result["dry_run"] += 1
            else:
                if max_alt_characters is None:
                    max_alt_characters = await mastodon.max_media_description_characters()
                if not event.mastodon_media_id:
                    media = await mastodon.upload_media(
                        screenshots.read(event.screenshot_path),
                        description=(event.screenshot_alt_text or "")[:max_alt_characters],
                    )
                    event.mastodon_media_id = media.id
                remote = await mastodon.create_status(
                    text,
                    visibility=policy.default_visibility,
                    language=policy.language,
                    idempotency_key=mastodon_idempotency_key(event.id),
                    media_ids=[event.mastodon_media_id],
                )
                event.status = "PUBLISHED"
                event.published_at = _now()
                event.mastodon_status_id = remote.id
                event.mastodon_status_url = remote.url
                session.add(SocialPublication(
                    outbox_event_id=event.id,
                    platform=event.platform,
                    event_type=event.event_type,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    remote_id=remote.id,
                    remote_url=remote.url,
                    remote_media_id=event.mastodon_media_id,
                    content_hash=event.content_hash,
                    published_at=event.published_at,
                ))
                session.add(_audit(event, "MASTODON_STATUS_PUBLISHED"))
                result["published"] += 1
            event.last_error = None
            event.processing_started_at = None
            screenshots.remove(event.screenshot_path)
            event.screenshot_path = None
            await session.commit()
        except PublicationResourceGone as exc:
            event.status = "CANCELLED"
            event.processing_started_at = None
            event.last_error = str(exc)
            screenshots.remove(event.screenshot_path)
            event.screenshot_path = None
            session.add(_audit(event, "MASTODON_PUBLICATION_CANCELLED"))
            result["cancelled"] += 1
            await session.commit()
        except (MastodonError, ScreenshotError) as exc:
            event.processing_started_at = None
            kind = "SCREENSHOT" if isinstance(exc, ScreenshotError) else exc.status_code or "NETWORK"
            event.last_error = f"{kind}: {str(exc)[:500]}"
            retryable = exc.retryable
            if retryable and event.attempt_count < settings.mastodon_max_attempts:
                retry_after = exc.retry_after if isinstance(exc, MastodonError) else None
                delay = retry_after or RETRY_DELAYS[
                    min(event.attempt_count - 1, len(RETRY_DELAYS) - 1)
                ]
                event.status = "PENDING_APPROVAL" if approval_required else "PENDING"
                event.next_attempt_at = _now() + timedelta(seconds=delay)
                result["retried"] += 1
            else:
                event.status = "FAILED"
                session.add(_audit(event, "MASTODON_PUBLICATION_FAILED"))
                result["failed"] += 1
            await session.commit()
    return result


async def publication_counts(session: AsyncSession) -> dict[str, int]:
    rows = (await session.execute(select(SocialPublicationOutbox.status, func.count()).group_by(SocialPublicationOutbox.status))).all()
    return {status: int(count) for status, count in rows}


def page_count(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))

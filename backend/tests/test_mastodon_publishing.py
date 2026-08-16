import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import Settings
from app.integrations.mastodon import MastodonClient, MastodonError
from app.models.analysis_area import AnalysisArea
from app.models.social_publication import SocialPublicationOutbox, SocialPublishingSettings
from app.services.social_policy import default_social_settings
from app.services.social_publishing import (
    PUBLISHABLE_AREA_FIELDS,
    _audit,
    enqueue_area_publication,
    enqueue_statistics_summary,
    fit_status,
    mastodon_idempotency_key,
    render_area_post,
)
from app.services.social_screenshots import ScreenshotError, ScreenshotService, screenshot_target


def settings(**overrides: object) -> Settings:
    values = {
        "mastodon_enabled": True,
        "mastodon_access_token": "test-token",
        "mastodon_area_update_debounce_seconds": 300,
        "app_base_url": "https://stadtplaner.oklabflensburg.de",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def area(**overrides: object) -> AnalysisArea:
    values = {
        "id": 1,
        "uuid": uuid.uuid4(),
        "slug": "innenstadt-1",
        "name": "Innenstadt",
        "area_type": "DISTRICT",
        "geometry": "MULTIPOLYGON EMPTY",
        "centroid": "POINT EMPTY",
        "area_m2": 123.0,
        "source": "OSM",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return AnalysisArea(**values)


@pytest.mark.asyncio
async def test_client_posts_with_minimal_scope_fields_and_stable_idempotency_header() -> None:
    event_id = uuid.uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/statuses"
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["idempotency-key"] == mastodon_idempotency_key(event_id)
        assert b"visibility=public" in request.content
        assert b"language=de" in request.content
        return httpx.Response(201, json={"id": "123", "url": "https://example.test/@ok/123"})

    client = MastodonClient("https://example.test", "test-token", transport=httpx.MockTransport(handler))
    result = await client.create_status("Hallo", visibility="public", language="de", idempotency_key=mastodon_idempotency_key(event_id))
    assert result.id == "123"
    assert len(mastodon_idempotency_key(event_id)) == 64
    assert mastodon_idempotency_key(event_id) == mastodon_idempotency_key(event_id)


@pytest.mark.asyncio
async def test_client_uploads_screenshot_with_alt_text_and_attaches_media() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v2/media":
            assert b'name="description"' in request.content
            assert b"Gebietsseite" in request.content
            assert b'image/jpeg' in request.content
            return httpx.Response(200, json={"id": "media-1", "url": "https://media.test/1"})
        assert request.url.path == "/api/v1/statuses"
        assert b"media_ids%5B%5D=media-1" in request.content
        return httpx.Response(201, json={"id": "status-1", "url": "https://example.test/1"})

    client = MastodonClient("https://example.test", "test-token", transport=httpx.MockTransport(handler))
    media = await client.upload_media(b"jpeg", description="Screenshot der Gebietsseite")
    await client.create_status(
        "Hallo",
        visibility="public",
        language="de",
        idempotency_key="stable",
        media_ids=[media.id],
    )
    assert [request.url.path for request in requests] == ["/api/v2/media", "/api/v1/statuses"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status,retryable", [(401, False), (403, False), (422, False), (429, True), (500, True)])
async def test_client_classifies_mastodon_errors(status: int, retryable: bool) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"Retry-After": "120"}, json={"error": "safe error"})

    client = MastodonClient("https://example.test", "test-token", transport=httpx.MockTransport(handler))
    with pytest.raises(MastodonError) as raised:
        await client.create_status("Hallo", visibility="public", language="de", idempotency_key="key")
    assert raised.value.retryable is retryable
    assert raised.value.retry_after == 120
    assert "test-token" not in str(raised.value)


@pytest.mark.asyncio
async def test_client_marks_timeout_retryable() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = MastodonClient("https://example.test", "test-token", transport=httpx.MockTransport(handler))
    with pytest.raises(MastodonError) as raised:
        await client.verify_credentials()
    assert raised.value.retryable is True


def test_area_template_uses_only_controlled_public_teaser_and_canonical_url() -> None:
    model = area(name="Innenstadt @someone #spam <script>")
    text = render_area_post(model, "AREA_PUBLIC_DATA_UPDATED", {"name", "internal_note"}, settings())
    assert "https://stadtplaner.oklabflensburg.de/gebiete/innenstadt-1" in text
    assert "@someone" not in text
    assert "#spam" not in text
    assert "<script>" not in text
    for secret in ("owner_address", "rent", "internal_note", "email", "user_id"):
        assert secret not in text
    assert "internal_note" not in PUBLISHABLE_AREA_FIELDS
    assert len(fit_status(text * 10, 500)) <= 500


@pytest.mark.asyncio
async def test_public_updates_coalesce_but_private_or_disabled_updates_do_not_enqueue() -> None:
    model = area()
    session = MagicMock()
    policy = default_social_settings(settings())
    session.scalar = AsyncMock(side_effect=[policy, None])
    first = await enqueue_area_publication(session, model, "AREA_PUBLIC_DATA_UPDATED", {"name", "internal_note"}, settings=settings())
    assert first is not None
    assert first.payload == {"changed_fields": ["name"], "approval_required": False}
    session.add.assert_called_once_with(first)

    existing = SocialPublicationOutbox(
        id=uuid.uuid4(), event_type="AREA_PUBLIC_DATA_UPDATED", resource_type="ANALYSIS_AREA",
        resource_id=model.uuid, payload={"changed_fields": ["name"]}, status="PENDING",
        next_attempt_at=datetime.now(UTC),
    )
    session.scalar.side_effect = [policy, existing]
    merged = await enqueue_area_publication(session, model, "AREA_BOUNDARY_UPDATED", {"geometry"}, settings=settings())
    assert merged is existing
    assert existing.event_type == "AREA_BOUNDARY_UPDATED"
    assert existing.payload["changed_fields"] == ["geometry", "name"]

    assert await enqueue_area_publication(session, model, "AREA_PUBLIC_DATA_UPDATED", {"internal_note"}, settings=settings()) is None
    assert await enqueue_area_publication(session, model, "AREA_PUBLIC_DATA_UPDATED", {"name"}, settings=settings(mastodon_enabled=False)) is None


@pytest.mark.asyncio
async def test_updates_for_different_areas_create_separate_events() -> None:
    first_area = area(name="Innenstadt")
    second_area = area(name="Nordstadt")
    session = MagicMock()
    policy = default_social_settings(settings())
    session.scalar = AsyncMock(side_effect=[policy, None, policy, None])

    first = await enqueue_area_publication(
        session, first_area, "AREA_PUBLIC_DATA_UPDATED", {"name"}, settings=settings(),
    )
    second = await enqueue_area_publication(
        session, second_area, "AREA_PUBLIC_DATA_UPDATED", {"name"}, settings=settings(),
    )

    assert first is not None and second is not None
    assert first.resource_id == first_area.uuid
    assert second.resource_id == second_area.uuid
    assert first.resource_id != second.resource_id
    assert session.add.call_count == 2


@pytest.mark.asyncio
async def test_bulk_statistics_import_creates_at_most_one_summary_event() -> None:
    session = MagicMock()
    policy = default_social_settings(settings())
    session.scalar = AsyncMock(side_effect=[policy, None])
    event = await enqueue_statistics_summary(session, 100, settings=settings())
    assert event is not None
    assert event.event_type == "AREA_STATISTICS_BULK_UPDATED"
    assert event.payload == {"changed_rows": 100, "approval_required": False}

    session.scalar.side_effect = [policy, event]
    same_event = await enqueue_statistics_summary(session, 50, settings=settings())
    assert same_event is event
    assert event.payload == {"changed_rows": 150, "approval_required": False}


def test_outbox_model_has_crash_safe_status_and_due_indexes() -> None:
    constraints = {constraint.name for constraint in SocialPublicationOutbox.__table__.constraints}
    indexes = {index.name: index for index in SocialPublicationOutbox.__table__.indexes}
    assert "ck_social_outbox_status" in constraints
    assert "idx_social_outbox_due" in indexes
    assert indexes["uq_social_outbox_pending_resource"].unique is True
    assert "screenshot_path" in SocialPublicationOutbox.__table__.columns
    assert "mastodon_media_id" in SocialPublicationOutbox.__table__.columns
    assert "ck_social_settings_approval" in {
        constraint.name for constraint in SocialPublishingSettings.__table__.constraints
    }


def test_social_audit_metadata_identifies_area_without_secrets() -> None:
    event = SocialPublicationOutbox(
        id=uuid.uuid4(), event_type="AREA_PUBLIC_DATA_UPDATED", resource_type="ANALYSIS_AREA",
        resource_id=uuid.uuid4(), payload={"changed_fields": ["name"]}, status="PUBLISHED",
        next_attempt_at=datetime.now(UTC), mastodon_status_url="https://example.test/@ok/123",
    )
    log = _audit(event, "MASTODON_STATUS_PUBLISHED")
    assert log.event_metadata == {
        "area_id": str(event.resource_id),
        "event_type": "AREA_PUBLIC_DATA_UPDATED",
        "mastodon_status_url": "https://example.test/@ok/123",
    }
    assert "token" not in str(log.event_metadata).lower()


def test_screenshot_target_is_public_deterministic_and_ssrf_protected(tmp_path) -> None:
    env = settings(mastodon_screenshot_directory=str(tmp_path))
    policy = default_social_settings(env)
    model = area(name="Innenstadt")
    event = SocialPublicationOutbox(
        id=uuid.uuid4(), event_type="AREA_PUBLIC_DATA_UPDATED", resource_type="ANALYSIS_AREA",
        resource_id=model.uuid, payload={"changed_fields": ["name"]}, status="PENDING",
        next_attempt_at=datetime.now(UTC),
    )
    target = screenshot_target(event, model, env, policy)
    assert target.url.startswith("https://stadtplaner.oklabflensburg.de/gebiete/innenstadt-1?")
    assert "Innenstadt" in target.alt_text
    service = ScreenshotService(env)
    service.validate_url(target.url)
    with pytest.raises(ScreenshotError):
        service.validate_url("https://attacker.example/admin/users")
    with pytest.raises(ScreenshotError):
        service.validate_url("https://stadtplaner.oklabflensburg.de/admin/social")

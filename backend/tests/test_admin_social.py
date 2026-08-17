import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import ValidationError

import app.api.admin as admin_api
import app.services.admin_social as admin_social_service
from app.auth.jwt import create_jwt
from app.core.config import Settings
from app.db.session import get_session
from app.main import app
from app.models.social_publication import SocialPublicationOutbox
from app.models.user import User
from app.schemas.social import (
    MastodonAdminStatusRead,
    SocialPublishingSettingsRead,
    SocialPublishingSettingsUpdate,
)
from app.services.admin_social import (
    _publication_actions,
    approve_social_publication,
    update_social_settings,
)
from app.services.social_policy import default_social_settings


class AuthSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get(self, _model: object, _key: object) -> User | None:
        return self.user


def user(*, superuser: bool = False) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(), email=f"user-{uuid.uuid4()}@example.org",
        first_name="Erika", last_name="Muster", is_active=True, is_verified=True,
        is_superuser=superuser, roles=[], created_at=now, updated_at=now,
    )


def access_cookie(actor: User | None) -> dict[str, str]:
    if actor is None:
        return {}
    token, _ = create_jwt(str(actor.id), "access", timedelta(minutes=5), {"email": actor.email, "role": "user"})
    return {"ocm_access_token": token}


async def status_request(actor: User | None, monkeypatch: pytest.MonkeyPatch) -> httpx.Response:
    async def override_session():
        yield AuthSession(actor)

    async def fake_status(_session: object) -> MastodonAdminStatusRead:
        return MastodonAdminStatusRead(
            enabled=True, configured=True, reachable=True,
            account="@oklabflensburg@norden.social",
            account_url="https://norden.social/@oklabflensburg",
            area_updates_enabled=True, dry_run=False, visibility="public",
            pending=1, failed=0, published=2,
        )

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(admin_api, "mastodon_admin_status", fake_status)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
            cookies=access_cookie(actor),
        ) as client:
            return await client.get("/api/v1/admin/social/mastodon/status")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_social_admin_status_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (await status_request(None, monkeypatch)).status_code == 401


@pytest.mark.asyncio
async def test_social_admin_status_rejects_normal_user(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (await status_request(user(), monkeypatch)).status_code == 403


@pytest.mark.asyncio
async def test_social_admin_status_rejects_verwaltung_without_superuser(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = user()
    actor.roles = ["VERWALTUNG"]
    assert (await status_request(actor, monkeypatch)).status_code == 403


@pytest.mark.asyncio
async def test_superuser_sees_status_but_never_token(monkeypatch: pytest.MonkeyPatch) -> None:
    response = await status_request(user(superuser=True), monkeypatch)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["account"] == "@oklabflensburg@norden.social"
    assert "token" not in response.text.lower()


def test_openapi_documents_superuser_only_social_endpoints() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/social/mastodon/status" in paths
    assert "/api/v1/admin/social/publications" in paths
    assert "/api/v1/admin/social/publications/{event_id}/retry" in paths
    assert paths["/api/v1/admin/social/publications/{event_id}/retry"]["post"]["security"]
    assert "/api/v1/admin/social/settings" in paths
    assert paths["/api/v1/admin/social/settings"]["patch"]["security"]
    assert "/api/v1/admin/social/publications/{event_id}/preview" in paths
    assert "/api/v1/admin/social/publications/{event_id}/approve" in paths
    assert "/api/v1/admin/social/publications/{event_id}/approve-and-publish" in paths
    assert "/api/v1/admin/social/publications/{event_id}/cancel" in paths


def social_runtime_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "mastodon_enabled": True,
        "mastodon_access_token": "test-token",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def pending_approval_event() -> SocialPublicationOutbox:
    return SocialPublicationOutbox(
        id=uuid.uuid4(),
        event_type="AREA_CREATED",
        resource_type="ANALYSIS_AREA",
        resource_id=uuid.uuid4(),
        payload={"approval_required": True},
        status="PENDING_APPROVAL",
        attempt_count=0,
        next_attempt_at=datetime.now(UTC),
        screenshot_path=None,
    )


@pytest.mark.asyncio
async def test_approve_and_publish_does_not_require_a_prepared_screenshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = pending_approval_event()
    actor = user(superuser=True)
    env = social_runtime_settings()
    policy = default_social_settings(env)
    policy.approval_mode = "MANUAL"
    session = MagicMock()
    session.get = AsyncMock(return_value=event)
    session.commit = AsyncMock()

    async def fake_policy(*_args: object, **_kwargs: object) -> object:
        return policy

    monkeypatch.setattr(admin_social_service, "get_settings", lambda: env)
    monkeypatch.setattr(admin_social_service, "get_social_settings", fake_policy)

    await approve_social_publication(session, event.id, actor, alt_text=None)
    await approve_social_publication(session, event.id, actor, alt_text=None)

    assert event.status == "PENDING"
    assert event.screenshot_path is None
    assert event.payload["approval_required"] is False
    assert event.payload["approved_by_user_id"] == str(actor.id)
    approval_audits = [
        added
        for added in (call.args[0] for call in session.add.call_args_list)
        if added.action == "MASTODON_PUBLICATION_APPROVED"
    ]
    assert len(approval_audits) == 1


def test_backend_policy_allows_direct_approval_and_explains_paused_state() -> None:
    event = pending_approval_event()
    env = social_runtime_settings()
    policy = default_social_settings(env)
    policy.approval_mode = "MANUAL"

    actions, reasons = _publication_actions(
        event, slug="innenstadt", settings=env, policy=policy
    )
    assert "APPROVE_AND_PUBLISH" in actions
    assert reasons == []

    policy.enabled = False
    actions, reasons = _publication_actions(
        event, slug="innenstadt", settings=env, policy=policy
    )
    assert "APPROVE_AND_PUBLISH" not in actions
    assert [(reason.code, reason.message) for reason in reasons] == [
        ("PUBLISHING_PAUSED", "Social Publishing ist pausiert.")
    ]


@pytest.mark.asyncio
async def test_approve_and_publish_endpoint_rejects_normal_users() -> None:
    actor = user()

    async def override_session():
        yield AuthSession(actor)

    app.dependency_overrides[get_session] = override_session
    try:
        cookies = {**access_cookie(actor), "ocm_csrf_token": "csrf-token"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
            headers={"x-csrf-token": "csrf-token"},
        ) as client:
            response = await client.post(
                f"/api/v1/admin/social/publications/{uuid.uuid4()}/approve-and-publish",
                json={},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_settings_backend_rejects_unknown_event_names() -> None:
    payload = SocialPublishingSettingsUpdate(
        enabled_events=["MY_RANDOM_EVENT"],
    )
    with pytest.raises(ValueError, match="Unknown social publication events"):
        await update_social_settings(AuthSession(user(superuser=True)), payload, user(superuser=True))


def test_settings_patch_accepts_partial_fields_and_rejects_empty_or_null() -> None:
    payload = SocialPublishingSettingsUpdate(default_visibility="unlisted")
    assert payload.model_dump(exclude_unset=True) == {"default_visibility": "unlisted"}

    with pytest.raises(ValidationError, match="Mindestens eine"):
        SocialPublishingSettingsUpdate()
    with pytest.raises(ValidationError, match="dürfen nicht null sein"):
        SocialPublishingSettingsUpdate(enabled=None)


async def settings_patch_request(
    actor: User,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> httpx.Response:
    async def override_session():
        yield AuthSession(actor)

    async def fake_update(
        _session: object,
        update: SocialPublishingSettingsUpdate,
        _actor: User,
    ) -> SocialPublishingSettingsRead:
        values = update.model_dump(exclude_unset=True)
        return SocialPublishingSettingsRead(
            enabled=bool(values.get("enabled", True)),
            approval_mode=str(values.get("approval_mode", "AUTOMATIC")),
            default_visibility=str(values.get("default_visibility", "public")),
            language="de",
            debounce_seconds=int(values.get("debounce_seconds", 300)),
            default_hashtags=list(values.get("default_hashtags", ["Flensburg"])),
            enabled_events=list(values.get("enabled_events", ["AREA_CREATED"])),
            screenshot_viewport=str(values.get("screenshot_viewport", "LANDSCAPE_16_9")),
            screenshot_show_map=bool(values.get("screenshot_show_map", True)),
            screenshot_show_facts=bool(values.get("screenshot_show_facts", True)),
            screenshot_show_pois=bool(values.get("screenshot_show_pois", False)),
            screenshot_show_branding=bool(values.get("screenshot_show_branding", True)),
            registry=[],
            updated_at=datetime.now(UTC),
        )

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(admin_api, "update_social_settings", fake_update)
    try:
        cookies = {**access_cookie(actor), "ocm_csrf_token": "csrf-token"}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
            headers={"x-csrf-token": "csrf-token"},
        ) as client:
            return await client.patch("/api/v1/admin/social/settings", json=payload)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_settings_patch_is_superuser_only(monkeypatch: pytest.MonkeyPatch) -> None:
    normal = user()
    assert (await settings_patch_request(normal, monkeypatch, {"enabled": False})).status_code == 403
    normal.roles = ["VERWALTUNG"]
    assert (await settings_patch_request(normal, monkeypatch, {"enabled": False})).status_code == 403

    response = await settings_patch_request(user(superuser=True), monkeypatch, {"enabled": False})
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_openapi_describes_partial_social_settings_update() -> None:
    operation = app.openapi()["paths"]["/api/v1/admin/social/settings"]["patch"]
    assert "Partially update social publishing settings" in operation["description"]


@pytest.mark.asyncio
async def test_settings_patch_batches_changed_fields_into_one_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = SimpleNamespace(
        enabled=True,
        approval_mode="AUTOMATIC",
        default_visibility="public",
        language="de",
        debounce_seconds=300,
        default_hashtags=["Flensburg"],
        enabled_events=["AREA_CREATED"],
        screenshot_viewport="LANDSCAPE_16_9",
        screenshot_show_map=True,
        screenshot_show_facts=True,
        screenshot_show_pois=False,
        screenshot_show_branding=True,
        updated_by_user_id=None,
        updated_at=datetime.now(UTC),
    )

    class SettingsSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

        async def commit(self) -> None:
            return None

        async def refresh(self, _value: object) -> None:
            return None

    async def fake_get_settings(*_args: object, **_kwargs: object) -> object:
        return model

    monkeypatch.setattr(admin_social_service, "get_social_settings", fake_get_settings)
    session = SettingsSession()
    await update_social_settings(
        session,  # type: ignore[arg-type]
        SocialPublishingSettingsUpdate(
            approval_mode="MANUAL",
            default_visibility="unlisted",
            screenshot_show_pois=True,
        ),
        user(superuser=True),
    )

    assert len(session.added) == 1
    audit = session.added[0]
    assert audit.action == "SOCIAL_PUBLISHING_SETTINGS_UPDATED"  # type: ignore[attr-defined]
    assert audit.event_metadata["changed_fields"] == [  # type: ignore[attr-defined]
        "approval_mode", "default_visibility", "screenshot_show_pois",
    ]
    assert audit.event_metadata["before"]["default_visibility"] == "public"  # type: ignore[attr-defined]
    assert audit.event_metadata["after"]["default_visibility"] == "unlisted"  # type: ignore[attr-defined]

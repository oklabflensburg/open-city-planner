import urllib.parse
import uuid
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

import app.api.auth as auth_api
from app.auth import oauth
from app.core.config import Settings
from app.main import app
from app.models.oauth_account import UserOAuthAccount
from app.models.user import User


def settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_only_fully_configured_providers_are_enabled() -> None:
    configured = settings(
        github_client_id="github-id",
        github_client_secret="github-secret",
        google_client_id="google-id",
        google_client_secret="google-secret",
    )
    github_only = settings(
        github_client_id="github-id",
        github_client_secret="github-secret",
        google_client_id="google-id",
    )

    assert configured.configured_oauth_providers == ["github", "google"]
    assert github_only.configured_oauth_providers == ["github"]
    assert settings().configured_oauth_providers == []


@pytest.mark.asyncio
async def test_provider_discovery_returns_labels_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_api, "configured_providers", lambda: ["github", "google"])

    response = await auth_api.get_oauth_providers()
    serialized = [provider.model_dump() for provider in response]

    assert serialized == [
        {"id": "github", "label": "GitHub"},
        {"id": "google", "label": "Google"},
    ]
    assert "secret" not in str(serialized).lower()


def test_oauth_login_and_callback_routes_are_registered() -> None:
    oauth_paths = {path for path in app.openapi()["paths"] if "oauth" in path}

    assert "/api/v1/auth/oauth/providers" in oauth_paths
    assert "/api/v1/auth/oauth/{provider}/login" in oauth_paths
    assert "/api/v1/auth/oauth/{provider}/link" in oauth_paths
    assert "/api/v1/auth/oauth/{provider}/callback" in oauth_paths


@pytest.mark.parametrize(
    ("provider", "expected_host", "expected_scope"),
    [
        ("github", "github.com", "read:user user:email"),
        ("google", "accounts.google.com", "openid email profile"),
    ],
)
def test_provider_login_urls_use_registered_callback(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected_host: str,
    expected_scope: str,
) -> None:
    configured = settings(
        api_base_url="https://api.example.org",
        github_client_id="github-id",
        github_client_secret="github-secret",
        google_client_id="google-id",
        google_client_secret="google-secret",
    )
    monkeypatch.setattr(oauth, "get_settings", lambda: configured)

    url = urllib.parse.urlparse(oauth.authorization_url(provider, "random-state"))
    query = urllib.parse.parse_qs(url.query)

    assert url.netloc == expected_host
    assert query["redirect_uri"] == [
        f"https://api.example.org/api/v1/auth/oauth/{provider}/callback"
    ]
    assert query["scope"] == [expected_scope]
    assert query["state"] == ["random-state"]


@pytest.mark.parametrize(
    ("redirect", "expected"),
    [
        ("/profil", "/profil"),
        ("/?polygon=123", "/?polygon=123"),
        ("https://evil.example", "/"),
        ("//evil.example", "/"),
        ("/\\evil.example", "/"),
        ("javascript:alert(1)", "/"),
    ],
)
def test_safe_redirect_path(redirect: str, expected: str) -> None:
    assert oauth.safe_redirect_path(redirect) == expected


def test_oauth_flow_cookie_is_signed_and_bound_to_user(monkeypatch: pytest.MonkeyPatch) -> None:
    configured = settings(jwt_secret_key="test-secret-at-least-32-bytes-long")
    monkeypatch.setattr(oauth, "get_settings", lambda: configured)
    flow = oauth.OAuthFlowState(
        state="random-state",
        mode="link",
        redirect_path="/profil",
        user_id="user-1",
    )

    encoded = oauth.encode_oauth_flow(flow)

    assert oauth.decode_oauth_flow(encoded) == flow
    assert oauth.decode_oauth_flow(f"{encoded[:-1]}x") is None


@pytest.mark.asyncio
async def test_link_callback_errors_return_to_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    configured = oauth_settings()
    monkeypatch.setattr(oauth, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "provider_is_configured", lambda _provider: True)
    cookie = oauth.encode_oauth_flow(
        oauth.OAuthFlowState("random-state", "link", "/profil", "user-1")
    )
    request = request_with_cookie(oauth.oauth_cookie_name("github"), cookie)

    response = await auth_api.oauth_callback(
        "github",
        "random-state",
        object(),  # type: ignore[arg-type]
        request,
        Response(),
        error="access_denied",
    )

    assert response.headers["location"] == (
        "http://localhost:3001/profil?provider=github&oauth_link_error=OAUTH_ACCESS_DENIED"
    )
    assert "ocm_oauth_state_github=" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_link_callback_keeps_bound_user_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = oauth_settings()
    user = User(id=uuid.uuid4(), email="user@example.org", is_active=True)
    identity = oauth.OAuthIdentity(
        provider="github",
        subject="github-user",
        email="user@example.org",
        email_verified=True,
    )
    linked = []

    async def record_link(_session: object, linked_user: User, linked_identity: object) -> None:
        linked.append((linked_user, linked_identity))

    monkeypatch.setattr(oauth, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "provider_is_configured", lambda _provider: True)
    monkeypatch.setattr(auth_api, "exchange_oauth_code", async_return(identity))
    monkeypatch.setattr(auth_api, "get_optional_user", async_return(user))
    monkeypatch.setattr(auth_api, "link_oauth_account", record_link)
    cookie = oauth.encode_oauth_flow(
        oauth.OAuthFlowState("random-state", "link", "/profil", str(user.id))
    )
    request = request_with_cookie(oauth.oauth_cookie_name("github"), cookie)

    response = await auth_api.oauth_callback(
        "github",
        "random-state",
        object(),  # type: ignore[arg-type]
        request,
        Response(),
        code="oauth-code",
    )

    assert linked == [(user, identity)]
    assert response.headers["location"] == (
        "http://localhost:3001/profil?provider=github&oauth_link=success"
    )


@pytest.mark.asyncio
async def test_link_callback_rejects_a_different_authenticated_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = oauth_settings()
    current_user = User(id=uuid.uuid4(), email="other@example.org", is_active=True)
    identity = oauth.OAuthIdentity(provider="github", subject="github-user")
    link_mock = AsyncMock()
    monkeypatch.setattr(oauth, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "provider_is_configured", lambda _provider: True)
    monkeypatch.setattr(auth_api, "exchange_oauth_code", async_return(identity))
    monkeypatch.setattr(auth_api, "get_optional_user", async_return(current_user))
    monkeypatch.setattr(auth_api, "link_oauth_account", link_mock)
    cookie = oauth.encode_oauth_flow(
        oauth.OAuthFlowState("random-state", "link", "/profil", str(uuid.uuid4()))
    )
    request = request_with_cookie(oauth.oauth_cookie_name("github"), cookie)

    response = await auth_api.oauth_callback(
        "github",
        "random-state",
        object(),  # type: ignore[arg-type]
        request,
        Response(),
        code="oauth-code",
    )

    assert response.headers["location"] == (
        "http://localhost:3001/profil?provider=github&oauth_link_error=AUTH_REQUIRED"
    )
    link_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_endpoint_is_idempotent_for_connected_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = oauth_settings()
    user = User(id=uuid.uuid4(), email="user@example.org", is_active=True)
    account = UserOAuthAccount(
        user_id=user.id,
        provider="github",
        provider_subject="github-user",
    )
    monkeypatch.setattr(auth_api, "get_settings", lambda: configured)
    monkeypatch.setattr(auth_api, "provider_is_configured", lambda _provider: True)
    monkeypatch.setattr(auth_api, "get_for_user_provider", async_return(account))

    response = await auth_api.oauth_link("github", object(), user)  # type: ignore[arg-type]

    assert response.headers["location"] == (
        "http://localhost:3001/profil?provider=github&oauth_link=already_connected"
    )


def oauth_settings() -> Settings:
    return settings(
        app_base_url="http://localhost:3001",
        jwt_secret_key="test-secret-at-least-32-bytes-long",
        github_client_id="github-id",
        github_client_secret="github-secret",
    )


def request_with_cookie(name: str, value: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/oauth/github/callback",
            "headers": [(b"cookie", f"{name}={value}".encode())],
        }
    )


def async_return(value: object):
    async def inner(*_args: object, **_kwargs: object) -> object:
        return value

    return inner

import ipaddress
import urllib.parse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

import app.services.mastodon_sso as service
from app.core.config import Settings
from app.models.oauth_account import MastodonOAuthInstance, OAuthFlowGrant
from app.services.mastodon_sso import (
    MastodonCredentialCipher,
    MastodonInstanceInfo,
    MastodonSSOClient,
    create_mastodon_oauth_flow,
    get_or_register_mastodon_app,
    normalize_mastodon_instance,
)


@pytest.mark.parametrize(
    "value",
    [
        "norden.social",
        "https://norden.social",
        "https://NORDEN.social/",
        "@norden.social",
        "@name@norden.social",
    ],
)
def test_normalizes_supported_instance_inputs(value: str) -> None:
    assert normalize_mastodon_instance(value) == "https://norden.social"


@pytest.mark.parametrize(
    "value",
    [
        "http://localhost",
        "https://127.0.0.1",
        "https://192.168.1.1",
        "https://169.254.169.254",
        "file:///etc/passwd",
        "https://example.org/path",
    ],
)
def test_rejects_private_or_non_instance_urls(value: str) -> None:
    with pytest.raises(HTTPException):
        normalize_mastodon_instance(value)


async def public_resolver(
    _host: str,
    _port: int,
) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    return {ipaddress.ip_address("93.184.216.34")}


@pytest.mark.asyncio
async def test_validates_registers_and_reads_identity_without_email() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/.well-known/oauth-authorization-server":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://social.example/oauth/authorize",
                    "token_endpoint": "https://social.example/oauth/token",
                    "scopes_supported": ["profile"],
                },
            )
        if request.url.path == "/api/v2/instance":
            return httpx.Response(200, json={"domain": "social.example", "version": "4.4.0"})
        if request.url.path == "/api/v1/apps":
            return httpx.Response(200, json={"client_id": "client-id", "client_secret": "client-secret"})
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "short-lived-user-token"})
        if request.url.path == "/api/v1/accounts/verify_credentials":
            assert request.headers["Authorization"] == "Bearer short-lived-user-token"
            return httpx.Response(
                200,
                json={
                    "id": "42",
                    "username": "stadtfreund",
                    "acct": "stadtfreund",
                    "display_name": "Stadtfreund",
                    "avatar_static": "https://social.example/avatar.png",
                    "url": "https://social.example/@stadtfreund",
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = MastodonSSOClient(
        Settings(_env_file=None),
        transport=httpx.MockTransport(handler),
        resolver=public_resolver,
    )
    info = await client.validate_instance("https://social.example")
    client_id, client_secret = await client.register_application(info)
    identity = await client.exchange_code(
        service.MastodonAppCredentials(
            "https://social.example",
            client_id,
            client_secret,
            info.scope,
        ),
        "authorization-code",
        "pkce-verifier",
    )

    assert info.scope == "profile"
    assert identity.provider == "mastodon"
    assert identity.provider_instance == "https://social.example"
    assert identity.subject == "42"
    assert identity.username == "@stadtfreund@social.example"
    assert identity.email is None
    assert identity.email_verified is False
    assert requests == [
        ("GET", "/.well-known/oauth-authorization-server"),
        ("GET", "/api/v2/instance"),
        ("POST", "/api/v1/apps"),
        ("POST", "/oauth/token"),
        ("GET", "/api/v1/accounts/verify_credentials"),
    ]


@pytest.mark.asyncio
async def test_blocks_redirect_to_private_address() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/private"})

    client = MastodonSSOClient(
        Settings(_env_file=None),
        transport=httpx.MockTransport(handler),
        resolver=public_resolver,
    )

    with pytest.raises(HTTPException) as exc:
        await client.validate_instance("https://social.example")

    assert exc.value.detail["error"]["code"] == "MASTODON_INSTANCE_PRIVATE"


def test_encrypts_instance_credentials() -> None:
    key = Fernet.generate_key().decode()
    cipher = MastodonCredentialCipher(key)
    encrypted = cipher.encrypt("client-secret")

    assert encrypted != "client-secret"
    assert cipher.decrypt(encrypted) == "client-secret"


class FakeSession:
    def __init__(self) -> None:
        self.instance: MastodonOAuthInstance | None = None
        self.grants: list[OAuthFlowGrant] = []
        self.commits = 0

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def scalar(self, _statement: object) -> MastodonOAuthInstance | None:
        return self.instance

    def add(self, value: object) -> None:
        if isinstance(value, MastodonOAuthInstance):
            self.instance = value
        elif isinstance(value, OAuthFlowGrant):
            self.grants.append(value)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class FakeMastodonClient:
    def __init__(self) -> None:
        self.registrations = 0

    async def validate_instance(self, origin: str) -> MastodonInstanceInfo:
        return MastodonInstanceInfo(origin, "profile", "4.4.0")

    async def register_application(self, _info: MastodonInstanceInfo) -> tuple[str, str]:
        self.registrations += 1
        return "cached-client", "cached-secret"


@pytest.mark.asyncio
async def test_reuses_encrypted_application_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = Fernet.generate_key().decode()
    settings = Settings(_env_file=None, mastodon_sso_encryption_key=key)
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    session = FakeSession()
    client = FakeMastodonClient()
    cipher = MastodonCredentialCipher(key)

    first = await get_or_register_mastodon_app(
        session,  # type: ignore[arg-type]
        "https://social.example",
        client=client,  # type: ignore[arg-type]
        cipher=cipher,
    )
    second = await get_or_register_mastodon_app(
        session,  # type: ignore[arg-type]
        "https://social.example",
        client=client,  # type: ignore[arg-type]
        cipher=cipher,
    )

    assert first == second
    assert client.registrations == 1
    assert session.instance is not None
    assert session.instance.client_secret_encrypted != "cached-secret"


@pytest.mark.asyncio
async def test_oauth_flow_uses_s256_and_keeps_verifier_server_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = Fernet.generate_key().decode()
    settings = Settings(
        _env_file=None,
        mastodon_sso_encryption_key=key,
        api_base_url="https://api.example.org",
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    async def cached_app(*_args: object, **_kwargs: object) -> service.MastodonAppCredentials:
        return service.MastodonAppCredentials(
            "https://social.example",
            "client-id",
            "client-secret",
            "profile",
        )

    monkeypatch.setattr(service, "get_or_register_mastodon_app", cached_app)
    session = FakeSession()
    state, url = await create_mastodon_oauth_flow(
        session,  # type: ignore[arg-type]
        "social.example",
        mode="login",
        redirect_path="https://evil.example",
    )
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)

    assert query["state"] == [state]
    assert query["scope"] == ["profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert "code_challenge" in query
    assert session.grants[0].redirect_path == "/"
    assert session.grants[0].code_verifier not in url
    assert session.grants[0].state_hash != state

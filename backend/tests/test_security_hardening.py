import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api.auth import clear_mfa_cookie, mfa_challenge_token
from app.auth import csrf
from app.auth import jwt as jwt_service
from app.auth.dependencies import get_verified_user, require_superuser
from app.core.config import Settings
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MfaDisableRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.schemas.geojson import PolygonCreate, PolygonUpdate
from app.security.request_limits import RequestBodyLimitMiddleware
from app.services import auth_service, email_service, public_query_security, rate_limit


def request(
    *,
    method: str = "POST",
    headers: list[tuple[bytes, bytes]] | None = None,
    cookies: dict[str, str] | None = None,
    client: tuple[str, int] = ("127.0.0.1", 1234),
) -> Request:
    raw_headers = list(headers or [])
    if cookies:
        raw_headers.append(
            (b"cookie", "; ".join(f"{key}={value}" for key, value in cookies.items()).encode())
        )
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/v1/auth/mfa/verify",
            "headers": raw_headers,
            "client": client,
        }
    )


@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    rate_limit.reset_memory_rate_limits()


@pytest.mark.asyncio
async def test_memory_rate_limit_is_atomic_and_returns_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        auth_rate_limit_attempts=2,
        auth_rate_limit_window_seconds=60,
        auth_rate_limit_backend="memory",
        rate_limit_fail_closed=False,
        production=False,
        rate_limit_memory_max_keys=100,
    )
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)

    results = await asyncio.gather(
        *(rate_limit.check_rate_limit("shared", attempts=2) for _ in range(3)),
        return_exceptions=True,
    )

    failures = [result for result in results if isinstance(result, HTTPException)]
    assert len(failures) == 1
    assert failures[0].status_code == 429
    assert int(failures[0].headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_fails_closed_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        auth_rate_limit_attempts=2,
        auth_rate_limit_window_seconds=60,
        auth_rate_limit_backend="redis",
        rate_limit_fail_closed=True,
        production=True,
    )
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit, "_check_redis", AsyncMock(side_effect=ConnectionError))

    with pytest.raises(HTTPException) as exc_info:
        await rate_limit.check_rate_limit("login")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"]["code"] == "RATE_LIMIT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_uses_bounded_development_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        auth_rate_limit_attempts=1,
        auth_rate_limit_window_seconds=60,
        auth_rate_limit_backend="redis",
        rate_limit_fail_closed=False,
        production=False,
        rate_limit_memory_max_keys=100,
    )
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit, "_check_redis", AsyncMock(side_effect=ConnectionError))

    await rate_limit.check_rate_limit("login")
    with pytest.raises(HTTPException) as exc_info:
        await rate_limit.check_rate_limit("login")
    assert exc_info.value.status_code == 429


def test_forwarded_ip_is_only_used_for_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarded = [(b"x-forwarded-for", b"198.51.100.8, 10.0.0.2")]
    monkeypatch.setattr(
        rate_limit, "get_settings", lambda: SimpleNamespace(trusted_proxy_list=[])
    )
    assert rate_limit.client_ip(request(headers=forwarded, client=("10.0.0.2", 1234))) == "10.0.0.2"

    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: SimpleNamespace(trusted_proxy_list=["10.0.0.0/8"]),
    )
    assert rate_limit.client_ip(request(headers=forwarded, client=("10.0.0.2", 1234))) == "198.51.100.8"


@pytest.mark.asyncio
async def test_unverified_user_cannot_write_gis() -> None:
    user = SimpleNamespace(is_active=True, is_verified=False)
    csrf_request = request(headers=[(b"x-csrf-token", b"csrf")], cookies={"ocm_csrf_token": "csrf"})

    with pytest.raises(HTTPException) as exc_info:
        await get_verified_user(csrf_request, user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_mfa_challenge_uses_http_only_cookie_and_clear_matches_path() -> None:
    challenge = "x" * 32
    assert mfa_challenge_token(request(cookies={"ocm_mfa_challenge": challenge}), None) == challenge
    with pytest.raises(HTTPException) as exc_info:
        mfa_challenge_token(request(), None)
    assert exc_info.value.detail["error"]["code"] == "MFA_CHALLENGE_MISSING"

    from fastapi import Response

    response = Response()
    clear_mfa_cookie(response)
    cookie = response.headers["set-cookie"]
    assert "ocm_mfa_challenge=" in cookie
    assert "Max-Age=0" in cookie
    assert "Path=/api/v1/auth/mfa" in cookie


@pytest.mark.asyncio
async def test_superuser_policy_distinguishes_setup_and_reauthentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, require_mfa_for_superusers=True)
    monkeypatch.setattr("app.auth.dependencies.get_settings", lambda: settings)
    monkeypatch.setattr(jwt_service, "get_settings", lambda: settings)
    admin = SimpleNamespace(id=uuid.uuid4(), is_superuser=True)
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[None, None])

    with pytest.raises(HTTPException) as setup_error:
        await require_superuser(request(), db, admin)
    assert setup_error.value.detail["error"]["code"] == "MFA_SETUP_REQUIRED"

    db.scalar = AsyncMock(side_effect=["totp-id", None])
    with pytest.raises(HTTPException) as reauth_error:
        await require_superuser(request(), db, admin)
    assert reauth_error.value.detail["error"]["code"] == "MFA_REAUTH_REQUIRED"

    for factor in ("otp", "recovery"):
        access, _ = jwt_service.create_jwt(
            str(admin.id), "access", timedelta(minutes=5), {"amr": ["pwd", factor]}
        )
        db.scalar = AsyncMock(side_effect=["totp-id", None])
        assert (
            await require_superuser(
                request(cookies={settings.auth_access_cookie_name: access}), db, admin
            )
            is admin
        )


def test_jwt_rejects_wrong_issuer_audience_and_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, jwt_secret_key="j" * 64)
    monkeypatch.setattr(jwt_service, "get_settings", lambda: settings)
    token, _ = jwt_service.create_jwt("user", "access", timedelta(minutes=5))
    assert jwt_service.decode_jwt(token, "access")["sub"] == "user"

    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"], audience=settings.jwt_audience)
    for claim, value in (("iss", "https://wrong.invalid"), ("aud", "wrong")):
        changed = {**payload, claim: value}
        invalid = jwt.encode(changed, settings.jwt_secret_key, algorithm="HS256")
        with pytest.raises(jwt.InvalidTokenError):
            jwt_service.decode_jwt(invalid, "access")

    invalid_algorithm = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS384")
    with pytest.raises(jwt.InvalidTokenError):
        jwt_service.decode_jwt(invalid_algorithm, "access")


def test_refresh_origin_uses_exact_origin_or_referer(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="https://stadtplaner.example",
        app_base_url="https://stadtplaner.example",
        refresh_require_origin=True,
    )
    monkeypatch.setattr(csrf, "get_settings", lambda: settings)
    csrf.validate_refresh_origin(request(headers=[(b"origin", b"https://stadtplaner.example")]))
    csrf.validate_refresh_origin(
        request(headers=[(b"referer", b"https://stadtplaner.example/profil")])
    )
    for headers in ([], [(b"origin", b"https://evil.example")]):
        with pytest.raises(HTTPException) as exc_info:
            csrf.validate_refresh_origin(request(headers=headers))
        assert exc_info.value.detail["error"]["code"] == "CSRF_FAILED"


def test_password_fields_have_a_hard_upper_bound() -> None:
    too_long = "x" * 257
    payloads = [
        lambda: SignupRequest(email="user@example.org", password=too_long),
        lambda: LoginRequest(email="user@example.org", password=too_long),
        lambda: ResetPasswordRequest(token="x" * 32, password=too_long, password_confirm=too_long),
        lambda: ChangePasswordRequest(current_password=too_long, new_password="a" * 12, new_password_confirm="a" * 12),
        lambda: MfaDisableRequest(current_password=too_long, code="123456"),
    ]
    for build in payloads:
        with pytest.raises(ValidationError):
            build()


def polygon_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Test",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[9.0, 54.0], [9.1, 54.0], [9.1, 54.1], [9.0, 54.0]]],
        },
    }
    payload.update(overrides)
    return payload


def test_polygon_description_and_properties_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        PolygonCreate(**polygon_payload(description="x" * 10_001))

    monkeypatch.setattr(
        "app.schemas.geojson.get_settings",
        lambda: SimpleNamespace(polygon_properties_max_bytes=32),
    )
    with pytest.raises(ValidationError):
        PolygonCreate(**polygon_payload(properties={"text": "ü" * 32}))
    with pytest.raises(ValidationError):
        PolygonUpdate(properties={"text": "x" * 64})


@pytest.mark.asyncio
async def test_public_query_guard_applies_rate_limit_and_statement_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        public_query_rate_limit_attempts=120,
        public_query_rate_limit_window_seconds=60,
        public_query_timeout_ms=8_000,
        trusted_proxy_list=[],
    )
    check = AsyncMock()
    session = AsyncMock()
    monkeypatch.setattr(public_query_security, "get_settings", lambda: settings)
    monkeypatch.setattr(public_query_security, "check_rate_limit", check)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)

    await public_query_security.guard_public_query(request(), session, "analytics")

    check.assert_awaited_once()
    statement = str(session.execute.await_args.args[0])
    assert "set_config('statement_timeout'" in statement
    assert session.execute.await_args.args[1] == {"timeout": "8000ms"}


@pytest.mark.asyncio
async def test_body_limit_rejects_streamed_body_without_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.security.request_limits.get_settings",
        lambda: SimpleNamespace(
            avatar_max_file_size=64,
            upload_body_overhead_bytes=16,
            max_json_body_bytes=8,
        ),
    )
    downstream_called = False

    async def downstream(_scope: object, receive: object, _send: object) -> None:
        nonlocal downstream_called
        downstream_called = True
        while True:
            message = await receive()
            if not message.get("more_body"):
                break

    messages = iter(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ]
    )

    async def receive() -> dict[str, object]:
        return next(messages)

    sent: list[dict[str, object]] = []

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(downstream)
    scope = {"type": "http", "method": "POST", "path": "/api/v1/auth/login", "headers": []}
    await middleware(scope, receive, send)

    assert downstream_called
    assert sent[0]["status"] == 413
    body = json.loads(sent[1]["body"])
    assert body["detail"]["error"]["code"] == "REQUEST_TOO_LARGE"


@pytest.mark.asyncio
async def test_new_password_reset_invalidates_previous_tokens_transactionally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=uuid.uuid4(), is_active=True, email="user@example.org")
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar = AsyncMock(return_value=user)
    monkeypatch.setattr(auth_service, "get_user_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, "send_password_reset_email", lambda *_args: None)

    await auth_service.forgot_password(session, user.email, request())

    invalidation = str(session.execute.await_args.args[0])
    assert "UPDATE password_reset_tokens" in invalidation
    assert "invalidated_at" in invalidation
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_password_reset_rejects_invalidated_token_and_consumes_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    invalidated = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        used_at=None,
        invalidated_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    rejected_session = AsyncMock()
    rejected_session.scalar = AsyncMock(return_value=invalidated)
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.reset_password(rejected_session, "t" * 32, "safe-password-123")
    assert exc_info.value.detail["error"]["code"] == "INVALID_RESET_TOKEN"

    user = SimpleNamespace(id=invalidated.user_id, password_hash="old", updated_at=now)
    valid = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        used_at=None,
        invalidated_at=None,
        expires_at=now + timedelta(minutes=5),
    )
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[valid, user])
    monkeypatch.setattr(auth_service, "hash_password", lambda _password: "new-hash")
    monkeypatch.setattr(auth_service, "send_password_changed_email", lambda *_args: None)

    result = await auth_service.reset_password(session, "v" * 32, "safe-password-123")

    assert result is user
    assert user.password_hash == "new-hash"
    assert valid.used_at is not None
    statements = "\n".join(str(call.args[0]) for call in session.execute.await_args_list)
    assert "UPDATE password_reset_tokens" in statements
    assert "UPDATE user_sessions" in statements
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_password_change_revokes_all_session_families(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = SimpleNamespace(id=uuid.uuid4(), password_hash="old", updated_at=None)
    session = AsyncMock()
    monkeypatch.setattr(auth_service, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth_service, "hash_password", lambda _password: "new")
    monkeypatch.setattr(auth_service, "send_password_changed_email", lambda *_args: None)

    await auth_service.change_password(session, account, "current", "new-password-123")

    statement = str(session.execute.await_args.args[0])
    assert "UPDATE user_sessions" in statement
    assert "password_changed" in session.execute.await_args.args[0].compile().params.values()
    session.commit.assert_awaited_once()


def test_console_email_never_logs_recipient_or_sensitive_body(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger=email_service.logger.name)
    monkeypatch.setattr(
        email_service,
        "get_settings",
        lambda: SimpleNamespace(email_backend="console"),
    )
    secret = "password-reset-token-super-secret"

    email_service.send_email("private@example.org", "Passwort zurücksetzen", "<p>x</p>", secret)

    assert "private@example.org" not in caplog.text
    assert secret not in caplog.text
    assert "Passwort zurücksetzen" in caplog.text

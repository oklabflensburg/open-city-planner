import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from fastapi import Response
from pydantic import ValidationError
from starlette.requests import Request

from app.api import auth as auth_api
from app.auth.jwt import decode_jwt
from app.models.user import User
from app.schemas.auth import MfaVerifyRequest
from app.security import encryption
from app.services import mfa_service
from app.services.auth_service import create_session_record


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 1234),
        }
    )


def user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="mfa@example.org",
        password_hash="hash",
        first_name="Mfa",
        last_name="User",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        roles=[],
        created_at=now,
        updated_at=now,
    )


def test_mfa_secret_is_encrypted_at_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    key = encryption.Fernet.generate_key().decode()
    monkeypatch.setattr(encryption, "get_settings", lambda: SimpleNamespace(mfa_encryption_key=key))
    plaintext = pyotp.random_base32()

    encrypted = encryption.encrypt_mfa_secret(plaintext)

    assert encrypted != plaintext
    assert plaintext not in encrypted
    assert encryption.decrypt_mfa_secret(encrypted) == plaintext


def test_totp_accepts_small_clock_skew_and_rejects_old_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = pyotp.random_base32()
    current = 2_000_000_000
    monkeypatch.setattr(mfa_service, "utcnow", lambda: datetime.fromtimestamp(current, UTC))
    monkeypatch.setattr(
        mfa_service, "get_settings", lambda: SimpleNamespace(mfa_totp_valid_window=1)
    )
    totp = pyotp.TOTP(secret)

    assert mfa_service._matching_counter(secret, totp.at(current)) == current // 30
    assert mfa_service._matching_counter(secret, totp.at(current - 30)) == current // 30 - 1
    assert mfa_service._matching_counter(secret, totp.at(current - 90)) is None


def test_recovery_codes_are_random_formatted_and_only_hashed() -> None:
    codes = mfa_service.generate_recovery_codes()

    assert len(codes) == 10
    assert len(set(codes)) == len(codes)
    assert all(len(code) == 14 and code.count("-") == 2 for code in codes)
    assert all(mfa_service.recovery_code_hash(code) != code for code in codes)


def test_mfa_verify_schema_requires_exactly_one_factor() -> None:
    token = "x" * 32
    with pytest.raises(ValidationError):
        MfaVerifyRequest(challenge_token=token)
    with pytest.raises(ValidationError):
        MfaVerifyRequest(challenge_token=token, code="123456", recovery_code="AAAA-BBBB-CCCC")


def test_session_tokens_preserve_authentication_methods() -> None:
    access, refresh, _record = create_session_record(
        user(),
        request(),
        family_id=uuid.uuid4(),
        authenticated_at=1_999_999_999,
        amr=["pwd", "otp"],
    )

    assert decode_jwt(access, "access")["amr"] == ["pwd", "otp"]
    assert decode_jwt(refresh, "refresh")["amr"] == ["pwd", "otp"]


@pytest.mark.asyncio
async def test_password_login_with_mfa_does_not_issue_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    issue = AsyncMock()
    monkeypatch.setattr(auth_api, "check_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_api, "authenticate", AsyncMock(return_value=account))
    monkeypatch.setattr(auth_api, "user_requires_mfa", AsyncMock(return_value=True))
    monkeypatch.setattr(
        auth_api,
        "create_login_challenge",
        AsyncMock(return_value=SimpleNamespace(token="opaque", expires_in=300)),
    )
    monkeypatch.setattr(auth_api, "issue_session", issue)

    result = await auth_api.post_login(
        SimpleNamespace(email=account.email, password="password", remember=True),
        AsyncMock(),
        Response(),
        request(),
    )

    assert result.status == "mfa_required"
    issue.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_mfa_login_refreshes_user_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    challenge = SimpleNamespace(
        user_id=account.id,
        used_at=None,
        invalidated_at=None,
        expires_at=datetime.max.replace(tzinfo=UTC),
        attempt_count=0,
        primary_method="password",
    )
    method = SimpleNamespace()
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar = AsyncMock(side_effect=[challenge, method])
    session.get = AsyncMock(return_value=account)
    monkeypatch.setattr(
        mfa_service,
        "get_settings",
        lambda: SimpleNamespace(mfa_max_attempts=5),
    )
    monkeypatch.setattr(
        mfa_service,
        "_consume_factor",
        AsyncMock(return_value="totp"),
    )

    result = await mfa_service.verify_login_challenge(
        session,
        "challenge-token",
        code="123456",
        recovery_code=None,
    )

    assert result == (account, "totp", "password")
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(account)

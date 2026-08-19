import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pyotp
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from starlette.requests import Request

from app.api import auth as auth_api
from app.auth.jwt import decode_jwt
from app.models.user import User
from app.schemas.auth import MfaVerifyRequest
from app.security import encryption
from app.services import mfa_service, passkey_service
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


def request_with_mfa_cookie() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/mfa/challenge",
            "headers": [(b"cookie", b"ocm_mfa_challenge=oauth-challenge-token")],
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
    monkeypatch.setattr(auth_api, "check_rate_limit", AsyncMock())
    monkeypatch.setattr(auth_api, "authenticate", AsyncMock(return_value=account))
    monkeypatch.setattr(
        auth_api,
        "available_mfa_methods",
        AsyncMock(return_value=["passkey", "totp", "recovery_code"]),
    )
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
    assert result.preferred_method == "passkey"
    assert result.methods == ["passkey", "totp", "recovery_code"]
    issue.assert_not_awaited()


@pytest.mark.asyncio
async def test_oauth_challenge_metadata_comes_from_backend_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    details = mfa_service.ChallengeDetails(
        methods=["totp", "recovery_code"],
        preferred_method="totp",
        expires_in=240,
    )
    monkeypatch.setattr(auth_api, "check_rate_limit", AsyncMock())
    describe = AsyncMock(return_value=details)
    monkeypatch.setattr(auth_api, "login_challenge_details", describe)
    session = AsyncMock()

    result = await auth_api.get_mfa_challenge(session, request_with_mfa_cookie())

    assert result.methods == ["totp", "recovery_code"]
    assert result.preferred_method == "totp"
    assert result.expires_in == 240
    describe.assert_awaited_once_with(session, "oauth-challenge-token")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([uuid.uuid4(), uuid.uuid4(), uuid.uuid4()], ["passkey", "totp", "recovery_code"]),
        ([uuid.uuid4(), None], ["passkey"]),
        ([None, uuid.uuid4(), uuid.uuid4()], ["totp", "recovery_code"]),
        ([None, uuid.uuid4(), None], ["totp"]),
        ([None, None], []),
    ],
)
async def test_available_mfa_methods_reflect_only_usable_factors(
    rows: list[object | None], expected: list[str]
) -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=rows)

    methods = await mfa_service.available_mfa_methods(session, uuid.uuid4())

    assert methods == expected


@pytest.mark.parametrize(
    ("methods", "expected"),
    [
        (["passkey", "totp", "recovery_code"], "passkey"),
        (["totp", "recovery_code"], "totp"),
        (["recovery_code"], "recovery_code"),
    ],
)
def test_preferred_mfa_method_uses_secure_order(
    methods: list[mfa_service.MfaMethodName], expected: str
) -> None:
    assert mfa_service.preferred_mfa_method(methods) == expected


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


@pytest.mark.asyncio
async def test_parallel_passkey_and_totp_consume_login_challenge_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    challenge = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=account.id,
        used_at=None,
        invalidated_at=None,
        expires_at=datetime.max.replace(tzinfo=UTC),
        attempt_count=0,
        primary_method="password",
    )
    method = SimpleNamespace(user_id=account.id)
    ceremony = SimpleNamespace(user_id=account.id, mfa_challenge_id=challenge.id)
    lock = asyncio.Lock()

    class LockedSession:
        def __init__(self) -> None:
            self.scalar_calls = 0
            self.holds_lock = False

        async def scalar(self, _query: object) -> object:
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                await lock.acquire()
                self.holds_lock = True
                return challenge
            return method

        async def get(self, _model: object, _identifier: object) -> User:
            return account

        def add(self, _item: object) -> None:
            return None

        async def commit(self) -> None:
            if self.holds_lock:
                self.holds_lock = False
                lock.release()

        async def refresh(self, _item: object) -> None:
            return None

    monkeypatch.setattr(mfa_service, "get_settings", lambda: SimpleNamespace(mfa_max_attempts=5))
    monkeypatch.setattr(mfa_service, "_consume_factor", AsyncMock(return_value="totp"))
    monkeypatch.setattr(passkey_service, "_locked_ceremony", AsyncMock(return_value=ceremony))
    monkeypatch.setattr(
        passkey_service,
        "_verify_authentication",
        AsyncMock(return_value=(account, SimpleNamespace())),
    )
    sessions = [LockedSession(), LockedSession()]

    results = await asyncio.gather(
        mfa_service.verify_login_challenge(
            sessions[0],  # type: ignore[arg-type]
            "challenge-token",
            code="123456",
            recovery_code=None,
        ),
        passkey_service.verify_mfa(
            sessions[1],  # type: ignore[arg-type]
            "challenge-token",
            "ceremony-token",
            {},
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, tuple) for result in results) == 1
    conflicts = [result for result in results if isinstance(result, HTTPException)]
    assert len(conflicts) == 1
    assert conflicts[0].detail["error"]["code"] in {"MFA_CHALLENGE_USED", "MFA_CHALLENGE_INVALID"}

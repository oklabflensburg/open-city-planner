import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from webauthn.helpers.exceptions import InvalidAuthenticationResponse
from webauthn.helpers.structs import CredentialDeviceType

from app.models.admin_audit_log import AdminAuditLog
from app.models.mfa import UserWebAuthnCredential, WebAuthnChallenge
from app.models.user import User
from app.schemas.auth import PasskeyRead, PasskeyRegistrationVerifyRequest
from app.services import passkey_service


class ScalarRows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/passkeys/login/options",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 1234),
        }
    )


def user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="passkey@example.org",
        password_hash="hash",
        first_name="Passkey",
        last_name="User",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        roles=[],
        created_at=now,
        updated_at=now,
    )


def ceremony(
    account: User | None = None,
    *,
    used: bool = False,
    purpose: str = "passkey_authenticate",
) -> WebAuthnChallenge:
    return WebAuthnChallenge(
        id=uuid.uuid4(),
        user_id=account.id if account else None,
        token_hash="hash",
        challenge=b"server-challenge",
        purpose=purpose,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        used_at=datetime.now(UTC) if used else None,
        attempt_count=0,
    )


def credential(account: User, *, sign_count: int = 0) -> UserWebAuthnCredential:
    now = datetime.now(UTC)
    return UserWebAuthnCredential(
        id=uuid.uuid4(),
        user_id=account.id,
        credential_id=b"credential-id",
        public_key=b"cose-public-key",
        sign_count=sign_count,
        name="Laptop",
        created_at=now,
        updated_at=now,
    )


def session() -> AsyncMock:
    value = AsyncMock()
    value.add = MagicMock()
    return value


def test_passkey_response_serializes_database_uuid_and_hides_key_material() -> None:
    account = user()
    stored = credential(account)

    payload = PasskeyRead.model_validate(stored).model_dump(mode="json")

    assert payload["id"] == str(stored.id)
    assert "credential_id" not in payload
    assert "public_key" not in payload


def test_registration_name_is_trimmed_and_cannot_be_blank() -> None:
    request_payload = PasskeyRegistrationVerifyRequest(
        ceremony_token="x" * 32,
        credential={},
        name="  Mein Laptop  ",
    )

    assert request_payload.name == "Mein Laptop"
    with pytest.raises(ValidationError):
        PasskeyRegistrationVerifyRequest(
            ceremony_token="x" * 32,
            credential={},
            name="   ",
        )


@pytest.mark.asyncio
async def test_passwordless_options_use_discoverable_credentials_and_server_challenge() -> None:
    db = session()

    result = await passkey_service.authentication_options(db, request())

    assert result.token
    assert result.options["rpId"] == "localhost"
    assert result.options["userVerification"] == "required"
    assert result.options["allowCredentials"] == []
    records = [call.args[0] for call in db.add.call_args_list]
    stored = next(value for value in records if isinstance(value, WebAuthnChallenge))
    assert stored.challenge
    assert stored.token_hash != result.token
    assert stored.purpose == "passkey_authenticate"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_used_passkey_challenge_cannot_be_replayed() -> None:
    account = user()
    db = session()
    db.scalar.return_value = ceremony(account, used=True)

    with pytest.raises(HTTPException) as exc_info:
        await passkey_service.verify_passwordless_login(db, "token", {})

    assert exc_info.value.detail["error"]["code"] == "PASSKEY_CHALLENGE_INVALID"


@pytest.mark.asyncio
async def test_expired_passkey_challenge_is_invalidated() -> None:
    expired = ceremony()
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db = session()
    db.scalar.return_value = expired

    with pytest.raises(HTTPException) as exc_info:
        await passkey_service.verify_passwordless_login(db, "token", {})

    assert exc_info.value.detail["error"]["code"] == "PASSKEY_CHALLENGE_EXPIRED"
    assert expired.invalidated_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_registration_creates_credential_and_consumes_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    challenge = ceremony(account, purpose="passkey_register")
    db = session()
    db.scalar = AsyncMock(side_effect=[challenge, None, 0])
    monkeypatch.setattr(
        passkey_service,
        "verify_registration_response",
        MagicMock(
            return_value=SimpleNamespace(
                credential_id=b"new-credential",
                credential_public_key=b"new-public-key",
                sign_count=1,
                aaguid=None,
                credential_device_type=CredentialDeviceType.MULTI_DEVICE,
                credential_backed_up=True,
            )
        ),
    )

    result = await passkey_service.verify_registration(
        db,
        account,
        "token",
        {"response": {"transports": ["internal"]}},
        "Mein Telefon",
    )

    assert result.credential_id == b"new-credential"
    assert result.public_key == b"new-public-key"
    assert result.name == "Mein Telefon"
    assert result.backed_up is True
    assert challenge.used_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_registration_is_rejected_and_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    challenge = ceremony(account, purpose="passkey_register")
    db = session()
    db.scalar = AsyncMock(side_effect=[challenge, uuid.uuid4()])
    monkeypatch.setattr(
        passkey_service,
        "verify_registration_response",
        MagicMock(return_value=SimpleNamespace(credential_id=b"existing")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await passkey_service.verify_registration(db, account, "token", {}, None)

    assert exc_info.value.detail["error"]["code"] == "PASSKEY_ALREADY_REGISTERED"
    assert challenge.attempt_count == 1
    audits = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], AdminAuditLog)
    ]
    assert any(value.action == "PASSKEY_REGISTRATION_FAILED" for value in audits)


@pytest.mark.asyncio
async def test_valid_passkey_login_checks_origin_rp_and_updates_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    stored = credential(account, sign_count=2)
    challenge = ceremony()
    db = session()
    db.scalar = AsyncMock(side_effect=[challenge, stored])
    db.get = AsyncMock(return_value=account)
    verification = SimpleNamespace(
        new_sign_count=3,
        credential_device_type=CredentialDeviceType.SINGLE_DEVICE,
        credential_backed_up=False,
    )
    verify = MagicMock(return_value=verification)
    monkeypatch.setattr(passkey_service, "verify_authentication_response", verify)
    monkeypatch.setattr(
        passkey_service, "_credential_id", lambda _payload: stored.credential_id
    )

    result = await passkey_service.verify_passwordless_login(db, "token", {"response": {}})

    assert result is account
    assert stored.sign_count == 3
    assert stored.last_used_at is not None
    assert challenge.used_at is not None
    assert verify.call_args.kwargs["expected_origin"] == "http://localhost:3000"
    assert verify.call_args.kwargs["expected_rp_id"] == "localhost"
    assert verify.call_args.kwargs["require_user_verification"] is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_multi_device_counter_regression_is_audited_without_lowering_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    stored = credential(account, sign_count=8)
    challenge = ceremony()
    db = session()
    db.scalar = AsyncMock(side_effect=[challenge, stored])
    db.get = AsyncMock(return_value=account)
    monkeypatch.setattr(passkey_service, "_credential_id", lambda _payload: stored.credential_id)
    monkeypatch.setattr(
        passkey_service,
        "verify_authentication_response",
        MagicMock(
            return_value=SimpleNamespace(
                new_sign_count=0,
                credential_device_type=CredentialDeviceType.MULTI_DEVICE,
                credential_backed_up=True,
            )
        ),
    )

    await passkey_service.verify_passwordless_login(db, "token", {"response": {}})

    assert stored.sign_count == 8
    audits = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], AdminAuditLog)
    ]
    assert any(value.action == "PASSKEY_COUNTER_REGRESSION" for value in audits)


@pytest.mark.asyncio
async def test_invalid_signature_is_generic_and_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    account = user()
    stored = credential(account)
    challenge = ceremony()
    db = session()
    db.scalar = AsyncMock(side_effect=[challenge, stored])
    db.get = AsyncMock(return_value=account)
    monkeypatch.setattr(passkey_service, "_credential_id", lambda _payload: stored.credential_id)
    monkeypatch.setattr(
        passkey_service,
        "verify_authentication_response",
        MagicMock(side_effect=InvalidAuthenticationResponse("bad signature")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await passkey_service.verify_passwordless_login(db, "token", {"response": {}})

    assert exc_info.value.detail["error"]["code"] == "PASSKEY_VERIFICATION_FAILED"
    assert challenge.attempt_count == 1
    audits = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], AdminAuditLog)
    ]
    assert any(value.action == "PASSKEY_LOGIN_FAILED" for value in audits)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_last_passwordless_method_cannot_be_removed() -> None:
    account = user()
    account.password_hash = None
    stored = credential(account)
    db = session()
    db.scalar = AsyncMock(side_effect=[stored, None, None, None, None])

    with pytest.raises(HTTPException) as exc_info:
        await passkey_service.remove_passkey(db, account, stored.id)

    assert exc_info.value.detail["error"]["code"] == "PASSKEY_LAST_METHOD"
    db.delete.assert_not_awaited()

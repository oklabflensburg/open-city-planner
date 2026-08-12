import asyncio
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import app.services.auth_service as service
from app.models.user import User
from app.models.verification_token import EmailVerificationToken


def verification_state(
    *, verified: bool = False, used: bool = False, expired: bool = False
) -> tuple[User, EmailVerificationToken]:
    user_id = uuid.uuid4()
    user = User(id=user_id, email="user@example.org", is_verified=verified)
    token = EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash="hash",
        expires_at=service.utcnow() + timedelta(hours=-1 if expired else 1),
        used_at=service.utcnow() if used else None,
    )
    return user, token


def session_for(token: EmailVerificationToken | None, user: User | None) -> AsyncMock:
    session = AsyncMock()
    session.scalar.side_effect = [token] if token is None else [token, user]
    return session


@pytest.mark.asyncio
async def test_valid_token_verifies_user_and_marks_token_used() -> None:
    user, token = verification_state()
    session = session_for(token, user)

    result = await service.verify_email(session, "a-valid-random-token")

    assert result.status == "verified"
    assert result.changed_user_state is True
    assert user.is_verified is True
    assert token.used_at is not None
    session.commit.assert_awaited_once()
    assert all("FOR UPDATE" in str(call.args[0]) for call in session.scalar.await_args_list)


@pytest.mark.asyncio
async def test_same_token_is_idempotent_on_second_use() -> None:
    user, token = verification_state()
    first_session = session_for(token, user)
    second_session = session_for(token, user)

    first = await service.verify_email(first_session, "a-valid-random-token")
    first_used_at = token.used_at
    second = await service.verify_email(second_session, "a-valid-random-token")

    assert first.changed_user_state is True
    assert second.status == "already_verified"
    assert second.changed_user_state is False
    assert token.used_at == first_used_at


@pytest.mark.asyncio
async def test_already_verified_user_wins_over_used_or_expired_token() -> None:
    user, token = verification_state(verified=True, used=True, expired=True)
    session = session_for(token, user)

    result = await service.verify_email(session, "an-old-random-token")

    assert result.status == "already_verified"
    assert result.changed_user_state is False


@pytest.mark.asyncio
async def test_expired_token_is_rejected_for_unverified_user() -> None:
    user, token = verification_state(expired=True)
    session = session_for(token, user)

    with pytest.raises(HTTPException) as exc:
        await service.verify_email(session, "an-expired-random-token")

    assert exc.value.detail["error"]["code"] == "VERIFICATION_TOKEN_EXPIRED"
    assert user.is_verified is False
    assert token.used_at is None
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_token_is_rejected() -> None:
    session = session_for(None, None)

    with pytest.raises(HTTPException) as exc:
        await service.verify_email(session, "an-unknown-random-token")

    assert exc.value.detail["error"]["code"] == "VERIFICATION_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_used_token_with_unverified_user_reports_invalid_state() -> None:
    user, token = verification_state(used=True)
    session = session_for(token, user)

    with pytest.raises(HTTPException) as exc:
        await service.verify_email(session, "a-used-random-token")

    assert exc.value.detail["error"]["code"] == "VERIFICATION_STATE_INVALID"
    assert user.is_verified is False


@pytest.mark.asyncio
async def test_resend_for_verified_user_creates_neither_token_nor_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, _ = verification_state(verified=True)
    session = AsyncMock()
    session.scalar.return_value = user
    create_token = AsyncMock(return_value="token")
    send_email = Mock()
    monkeypatch.setattr(service, "create_verification_token", create_token)
    monkeypatch.setattr(service, "send_verification_email", send_email)

    sent = await service.resend_verification(session, user)

    assert sent is False
    create_token.assert_not_awaited()
    send_email.assert_not_called()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resend_for_unverified_user_sends_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, _ = verification_state()
    session = AsyncMock()
    session.scalar.return_value = user
    create_token = AsyncMock(return_value="token")
    send_email = Mock()
    monkeypatch.setattr(service, "create_verification_token", create_token)
    monkeypatch.setattr(service, "send_verification_email", send_email)

    sent = await service.resend_verification(session, user)

    assert sent is True
    create_token.assert_awaited_once_with(session, user)
    send_email.assert_called_once_with(user, "token")


class LockedSession:
    def __init__(
        self,
        lock: asyncio.Lock,
        token: EmailVerificationToken,
        user: User,
    ) -> None:
        self.lock = lock
        self.token = token
        self.user = user
        self.has_lock = False

    async def scalar(self, statement: object) -> object:
        if "email_verification_tokens" in str(statement):
            await self.lock.acquire()
            self.has_lock = True
            return self.token
        return self.user

    async def commit(self) -> None:
        await asyncio.sleep(0)
        if self.has_lock:
            self.lock.release()
            self.has_lock = False


@pytest.mark.asyncio
async def test_parallel_requests_only_change_user_state_once() -> None:
    user, token = verification_state()
    lock = asyncio.Lock()
    sessions = [LockedSession(lock, token, user), LockedSession(lock, token, user)]

    results = await asyncio.gather(
        *(service.verify_email(session, "the-same-random-token") for session in sessions)  # type: ignore[arg-type]
    )

    assert sorted(result.status for result in results) == ["already_verified", "verified"]
    assert sum(result.changed_user_state for result in results) == 1
    assert user.is_verified is True
    assert token.used_at is not None

import asyncio
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.api.auth import get_auth_session
from app.auth.jwt import create_jwt, decode_jwt
from app.auth.tokens import hash_token
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import AccountDeactivationReason, User
from app.models.user_session import UserSession
from app.services.auth_service import (
    create_session_record,
    refresh_session,
    revoke_current_session,
    utcnow,
)


def request() -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/refresh",
        "headers": [(b"user-agent", b"pytest")],
        "client": ("127.0.0.1", 1234),
    })


def user(*, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        email="refresh@example.org",
        password_hash="hash",
        first_name="Refresh",
        last_name="User",
        is_active=active,
        is_verified=True,
        is_superuser=False,
        roles=[],
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def refresh_record(account: User, *, expires_in: timedelta = timedelta(days=1)) -> tuple[str, UserSession]:
    token, jti = create_jwt(str(account.id), "refresh", expires_in)
    record = UserSession(
        id=uuid.uuid4(),
        user_id=account.id,
        token_hash=hash_token(token),
        jti=jti,
        family_id=uuid.uuid4(),
        expires_at=utcnow() + expires_in,
    )
    return token, record


def test_session_tokens_share_original_authentication_time() -> None:
    authenticated_at = int((utcnow() - timedelta(minutes=3)).timestamp())
    access_token, refresh_token, _record = create_session_record(
        user(), request(), family_id=uuid.uuid4(), authenticated_at=authenticated_at
    )

    assert decode_jwt(access_token, "access")["auth_time"] == authenticated_at
    assert decode_jwt(refresh_token, "refresh")["auth_time"] == authenticated_at


def session_for(record: UserSession | None, account: User | None) -> AsyncMock:
    session = AsyncMock()
    session.scalar.return_value = record
    session.get.return_value = account
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_valid_refresh_rotates_token_and_sets_new_cookies() -> None:
    account = user()
    token, record = refresh_record(account)
    session = session_for(record, account)
    response = Response()

    refreshed_user, csrf_token = await refresh_session(session, response, token, request())

    assert refreshed_user is account
    assert csrf_token
    assert record.revoked_at is not None
    assert record.rotated_at is not None
    assert record.revocation_reason == "rotated"
    assert record.replaced_by_jti
    next_records = [item for item in session.add.call_args_list if isinstance(item.args[0], UserSession)]
    assert len(next_records) == 1
    assert next_records[0].args[0].family_id == record.family_id
    assert response.headers.getlist("set-cookie")
    session.commit.assert_awaited_once()
    assert "FOR UPDATE" in str(session.scalar.await_args.args[0])


@pytest.mark.asyncio
async def test_expired_refresh_jwt_is_rejected() -> None:
    account = user()
    token, _ = refresh_record(account, expires_in=timedelta(seconds=-1))

    with pytest.raises(HTTPException) as exc:
        await refresh_session(AsyncMock(), Response(), token, request())

    assert exc.value.status_code == 401
    assert exc.value.detail["error"]["code"] == "REFRESH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_invalid_refresh_signature_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await refresh_session(AsyncMock(), Response(), "not-a-jwt", request())

    assert exc.value.status_code == 401
    assert exc.value.detail["error"]["code"] == "REFRESH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_revoked_refresh_session_is_rejected() -> None:
    account = user()
    token, record = refresh_record(account)
    record.revoked_at = utcnow()

    with pytest.raises(HTTPException) as exc:
        await refresh_session(session_for(record, account), Response(), token, request())

    assert exc.value.detail["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_inactive_user_revokes_token_family() -> None:
    account = user(active=False)
    token, record = refresh_record(account)
    session = session_for(record, account)

    with pytest.raises(HTTPException) as exc:
        await refresh_session(session, Response(), token, request())

    assert exc.value.detail["error"]["code"] == "ACCOUNT_DISABLED"
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_self_deactivated_user_refresh_returns_stable_status_without_login_audit() -> None:
    account = user(active=False)
    account.deactivation_reason = AccountDeactivationReason.SELF_DEACTIVATED
    token, record = refresh_record(account)
    session = session_for(record, account)

    with pytest.raises(HTTPException) as exc:
        await refresh_session(session, Response(), token, request())

    assert exc.value.detail["error"]["code"] == "ACCOUNT_SELF_DEACTIVATED"
    assert not any(
        isinstance(call.args[0], AdminAuditLog) and call.args[0].action == "LOGIN_BLOCKED"
        for call in session.add.call_args_list
    )
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_recent_concurrent_rotation_uses_grace_window() -> None:
    account = user()
    token, record = refresh_record(account)
    record.rotated_at = utcnow()
    record.revoked_at = record.rotated_at

    with pytest.raises(HTTPException) as exc:
        await refresh_session(session_for(record, account), Response(), token, request())

    assert exc.value.status_code == 409
    assert exc.value.detail["error"]["code"] == "REFRESH_ALREADY_ROTATED"


@pytest.mark.asyncio
async def test_two_parallel_refreshes_consume_the_token_only_once() -> None:
    account = user()
    token, record = refresh_record(account)
    lock = asyncio.Lock()

    class LockedSession:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.holds_lock = False

        async def scalar(self, _query: object) -> UserSession:
            await lock.acquire()
            self.holds_lock = True
            return record

        async def get(self, _model: object, _identifier: object) -> User:
            return account

        def add(self, item: object) -> None:
            self.added.append(item)

        async def commit(self) -> None:
            if self.holds_lock:
                self.holds_lock = False
                lock.release()

        async def execute(self, _query: object) -> None:
            return None

    sessions = [LockedSession(), LockedSession()]
    results = await asyncio.gather(
        *(refresh_session(session, Response(), token, request()) for session in sessions),  # type: ignore[arg-type]
        return_exceptions=True,
    )

    successes = [result for result in results if isinstance(result, tuple)]
    conflicts = [result for result in results if isinstance(result, HTTPException)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].status_code == 409
    assert sum(isinstance(item, UserSession) for session in sessions for item in session.added) == 1


@pytest.mark.asyncio
async def test_old_rotated_token_replay_revokes_family_and_is_audited() -> None:
    account = user()
    token, record = refresh_record(account)
    record.rotated_at = utcnow() - timedelta(minutes=1)
    record.revoked_at = record.rotated_at
    session = session_for(record, account)

    with pytest.raises(HTTPException) as exc:
        await refresh_session(session, Response(), token, request())

    assert exc.value.detail["error"]["code"] == "REFRESH_TOKEN_REUSE_DETECTED"
    session.execute.assert_awaited_once()
    audit_records = [item.args[0] for item in session.add.call_args_list]
    assert any(isinstance(item, AdminAuditLog) and item.action == "REFRESH_TOKEN_REUSE_DETECTED" for item in audit_records)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_revokes_the_whole_refresh_family() -> None:
    account = user()
    token, record = refresh_record(account)
    session = session_for(record, account)

    await revoke_current_session(session, token)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_endpoint_returns_user_and_csrf_after_hard_reload() -> None:
    account = user()
    response = Response()

    result = await get_auth_session(request(), response, account)

    assert result.user.id == account.id
    assert result.csrf_token
    assert any("ocm_csrf_token=" in value for value in response.headers.getlist("set-cookie"))

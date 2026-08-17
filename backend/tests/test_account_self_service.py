import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

import app.api.users as users_api
from app.auth.jwt import create_jwt
from app.db.session import get_session
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import User
from app.services import account_service
from app.services.account_service import deactivate_own_account, delete_own_account


def user(*, superuser: bool = False, password_hash: str | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"account-{uuid.uuid4()}@example.org",
        password_hash=password_hash,
        first_name="Account",
        last_name="Owner",
        avatar_url="/api/v1/media/avatars/avatar.webp",
        is_active=True,
        is_verified=True,
        is_superuser=superuser,
        roles=[],
        created_at=now,
        updated_at=now,
    )


class ScalarRows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


def service_session(
    account: User, *, active_superusers: list[uuid.UUID] | None = None
) -> AsyncMock:
    session = AsyncMock()
    session.scalar.return_value = account
    session.scalars.return_value = ScalarRows(active_superusers or [])
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_deactivation_uses_existing_active_state_revokes_sessions_and_audits() -> None:
    account = user()
    session = service_session(account)

    await deactivate_own_account(session, account.id)

    assert account.is_active is False
    statement = str(session.execute.await_args.args[0])
    assert "UPDATE user_sessions" in statement
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AdminAuditLog)
    assert audit.action == "ACCOUNT_DEACTIVATED"
    assert audit.actor_user_id == account.id
    assert audit.target_user_id == account.id
    assert audit.event_metadata == {"self_service": True}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_last_active_superuser_cannot_deactivate_or_delete() -> None:
    account = user(superuser=True)
    for action in ("deactivate", "delete"):
        session = service_session(account, active_superusers=[account.id])
        with pytest.raises(HTTPException) as exc_info:
            if action == "deactivate":
                await deactivate_own_account(session, account.id)
            else:
                await delete_own_account(
                    session,
                    account.id,
                    confirmation_text="LÖSCHEN",
                    current_password=None,
                    authenticated_at=datetime.now(UTC),
                    recent_auth_seconds=600,
                )
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"]["code"] == "LAST_SUPERUSER_REQUIRED"
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_requires_password_for_local_account(monkeypatch: pytest.MonkeyPatch) -> None:
    account = user(password_hash="stored-hash")
    session = service_session(account)
    monkeypatch.setattr(account_service, "verify_password", lambda *_args: False)

    with pytest.raises(HTTPException) as exc_info:
        await delete_own_account(
            session,
            account.id,
            confirmation_text="löschen",
            current_password="wrong",
            authenticated_at=datetime.now(UTC),
            recent_auth_seconds=600,
        )

    assert exc_info.value.detail["error"]["code"] == "INVALID_CURRENT_PASSWORD"
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_removes_personal_dependencies_and_keeps_audit_event() -> None:
    account = user()
    session = service_session(account)

    avatar_url = await delete_own_account(
        session,
        account.id,
        confirmation_text="löschen",
        current_password=None,
        authenticated_at=datetime.now(UTC),
        recent_auth_seconds=600,
    )

    sql = "\n".join(str(call.args[0]) for call in session.execute.await_args_list)
    assert "UPDATE user_polygons SET created_by_user_id" in sql
    assert "UPDATE user_polygons SET updated_by_user_id" in sql
    assert "UPDATE social_publishing_settings SET updated_by_user_id" in sql
    assert "DELETE FROM user_oauth_accounts" in sql
    assert "DELETE FROM user_sessions" in sql
    assert "DELETE FROM password_reset_tokens" in sql
    assert "DELETE FROM email_verification_tokens" in sql
    audit = session.add.call_args.args[0]
    assert audit.action == "ACCOUNT_DELETED"
    assert audit.actor_user_id is None
    assert audit.resource_id == account.id
    assert audit.event_metadata == {"self_service": True}
    session.delete.assert_awaited_once_with(account)
    session.commit.assert_awaited_once()
    assert avatar_url == account.avatar_url


@pytest.mark.asyncio
async def test_oauth_only_delete_rejects_old_access_authentication() -> None:
    account = user()
    session = service_session(account)

    with pytest.raises(HTTPException) as exc_info:
        await delete_own_account(
            session,
            account.id,
            confirmation_text="LÖSCHEN",
            current_password=None,
            authenticated_at=datetime.now(UTC) - timedelta(minutes=11),
            recent_auth_seconds=600,
        )

    assert exc_info.value.detail["error"]["code"] == "RECENT_AUTH_REQUIRED"


async def self_service_request(
    account: User,
    path: str,
    method: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    class AuthSession:
        async def get(self, _model: object, key: object) -> User | None:
            return account if key == account.id else None

    async def override_session():
        yield AuthSession()

    token, _ = create_jwt(str(account.id), "access", timedelta(minutes=5), {"email": account.email})
    cookies = {"ocm_access_token": token, "ocm_csrf_token": "csrf-token"}
    headers = {"x-csrf-token": "csrf-token"}
    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies
        ) as client:
            return await client.request(method, path, headers=headers, json=json)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_self_service_endpoints_only_pass_current_user_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = user()
    deactivated: list[uuid.UUID] = []
    deleted: list[uuid.UUID] = []

    async def fake_deactivate(_session: object, user_id: uuid.UUID) -> None:
        deactivated.append(user_id)

    async def fake_delete(_session: object, user_id: uuid.UUID, **_kwargs: object) -> None:
        deleted.append(user_id)

    monkeypatch.setattr(users_api, "deactivate_own_account", fake_deactivate)
    monkeypatch.setattr(users_api, "delete_own_account", fake_delete)
    monkeypatch.setattr(users_api, "delete_avatar_file", lambda _url: None)

    deactivate_response = await self_service_request(
        account, "/api/v1/users/me/deactivate", "POST", monkeypatch
    )
    delete_response = await self_service_request(
        account,
        "/api/v1/users/me",
        "DELETE",
        monkeypatch,
        json={"confirmation_text": "LÖSCHEN", "current_password": None},
    )

    assert deactivate_response.status_code == 200
    assert delete_response.status_code == 200
    assert deactivated == [account.id]
    assert deleted == [account.id]


def test_openapi_documents_self_service_account_operations() -> None:
    schema = app.openapi()["paths"]
    assert schema["/api/v1/users/me/deactivate"]["post"]["summary"] == (
        "Deactivate current user account"
    )
    assert schema["/api/v1/users/me"]["delete"]["summary"] == "Delete current user account"
    assert {"401", "409"}.issubset(schema["/api/v1/users/me/deactivate"]["post"]["responses"])
    assert {"401", "403", "409"}.issubset(schema["/api/v1/users/me"]["delete"]["responses"])

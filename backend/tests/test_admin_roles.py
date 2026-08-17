import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException

import app.api.admin as admin_api
from app.auth.jwt import create_jwt
from app.db.session import get_session
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import AccountDeactivationReason, User
from app.schemas.admin import AdminUserRead
from app.services.admin_users import assign_role, ensure_known_role, remove_role, set_user_active


class AuthSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get(self, _model: object, _key: object) -> User | None:
        return self.user


class RoleSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def execute(self, _statement: object) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1


def user(*, superuser: bool = False, roles: list[str] | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4()}@example.org",
        first_name="Max",
        last_name="Muster",
        is_active=True,
        is_verified=True,
        is_superuser=superuser,
        roles=roles or [],
        created_at=now,
        updated_at=now,
    )


def request_parts(actor: User | None) -> tuple[dict[str, str], dict[str, str]]:
    cookies = {"ocm_csrf_token": "csrf-token"}
    headers = {"x-csrf-token": "csrf-token"}
    if actor:
        token, _ = create_jwt(
            str(actor.id), "access", timedelta(minutes=5), {"email": actor.email, "role": "user"}
        )
        cookies["ocm_access_token"] = token
    return cookies, headers


async def admin_request(
    actor: User | None,
    path: str,
    *,
    method: str = "GET",
    include_csrf: bool = True,
    monkeypatch: pytest.MonkeyPatch,
) -> httpx.Response:
    async def override_session():
        yield AuthSession(actor)

    target = user()

    async def fake_list(*_args: object, **_kwargs: object):
        return ([AdminUserRead.model_validate(target)], 1)

    async def fake_get(*_args: object, **_kwargs: object):
        return target

    async def fake_mutation(*_args: object, **_kwargs: object):
        return True

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(admin_api, "list_users", fake_list)
    monkeypatch.setattr(admin_api, "get_admin_user", fake_get)
    monkeypatch.setattr(admin_api, "assign_role", fake_mutation)
    monkeypatch.setattr(admin_api, "remove_role", fake_mutation)
    cookies, headers = request_parts(actor)
    if not include_csrf:
        headers.pop("x-csrf-token", None)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies
        ) as client:
            return await client.request(method, path, headers=headers)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_users_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    response = await admin_request(None, "/api/v1/admin/users", monkeypatch=monkeypatch)
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("roles", [[], ["VERWALTUNG"]])
async def test_normal_and_verwaltung_users_are_forbidden(
    roles: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await admin_request(user(roles=roles), "/api/v1/admin/users", monkeypatch=monkeypatch)
    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "SUPERUSER_REQUIRED"


@pytest.mark.asyncio
async def test_superuser_can_list_users_without_sensitive_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = await admin_request(user(superuser=True), "/api/v1/admin/users", monkeypatch=monkeypatch)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    payload = response.json()
    assert payload["total"] == 1
    serialized = str(payload)
    for secret in ("password_hash", "token_hash", "oauth_token", "reset_token"):
        assert secret not in serialized


@pytest.mark.asyncio
async def test_only_superuser_can_mutate_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    target_id = uuid.uuid4()
    path = f"/api/v1/admin/users/{target_id}/roles/VERWALTUNG"
    forbidden = await admin_request(user(roles=["VERWALTUNG"]), path, method="PUT", monkeypatch=monkeypatch)
    allowed = await admin_request(user(superuser=True), path, method="PUT", monkeypatch=monkeypatch)
    assert forbidden.status_code == 403
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_role_mutation_requires_csrf(monkeypatch: pytest.MonkeyPatch) -> None:
    path = f"/api/v1/admin/users/{uuid.uuid4()}/roles/VERWALTUNG"
    response = await admin_request(
        user(superuser=True),
        path,
        method="PUT",
        include_csrf=False,
        monkeypatch=monkeypatch,
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "CSRF_FAILED"


def test_unknown_roles_are_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ensure_known_role("GOTT_MODUS")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"]["code"] == "ROLE_NOT_FOUND"


@pytest.mark.asyncio
async def test_assign_and_remove_role_are_idempotent_and_audited() -> None:
    actor = user(superuser=True)
    target = user()
    session = RoleSession()

    assert await assign_role(session, target, "verwaltung", actor) is True  # type: ignore[arg-type]
    assert target.roles == ["VERWALTUNG"]
    assert session.commits == 1
    assert isinstance(session.added[0], AdminAuditLog)
    assert session.added[0].action == "USER_ROLE_ASSIGNED"

    assert await assign_role(session, target, "VERWALTUNG", actor) is False  # type: ignore[arg-type]
    assert session.commits == 1

    assert await remove_role(session, target, "VERWALTUNG", actor) is True  # type: ignore[arg-type]
    assert target.roles == []
    assert session.commits == 2
    assert isinstance(session.added[1], AdminAuditLog)
    assert session.added[1].action == "USER_ROLE_REMOVED"


@pytest.mark.asyncio
async def test_role_change_immediately_changes_existing_permission_check() -> None:
    from app.auth.dependencies import has_role

    actor = user(superuser=True)
    target = user()
    session = RoleSession()
    assert has_role(target, "VERWALTUNG") is False
    await assign_role(session, target, "VERWALTUNG", actor)  # type: ignore[arg-type]
    assert has_role(target, "VERWALTUNG") is True
    await remove_role(session, target, "VERWALTUNG", actor)  # type: ignore[arg-type]
    assert has_role(target, "VERWALTUNG") is False


@pytest.mark.asyncio
async def test_superuser_cannot_disable_own_account() -> None:
    actor = user(superuser=True)
    with pytest.raises(HTTPException) as exc_info:
        await set_user_active(RoleSession(), actor, False, actor)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"]["code"] == "CANNOT_DISABLE_SELF"


@pytest.mark.asyncio
async def test_admin_status_change_tracks_and_clears_admin_deactivation_reason() -> None:
    actor = user(superuser=True)
    target = user()
    session = RoleSession()

    await set_user_active(session, target, False, actor)  # type: ignore[arg-type]
    assert target.deactivation_reason == AccountDeactivationReason.ADMIN_DEACTIVATED
    assert target.deactivated_at is not None

    await set_user_active(session, target, True, actor)  # type: ignore[arg-type]
    assert target.deactivation_reason is None
    assert target.deactivated_at is None

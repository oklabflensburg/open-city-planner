import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

import app.api.admin as admin_api
from app.auth.jwt import create_jwt
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.schemas.admin import (
    AuditLogActor,
    AuditLogListItem,
    AuditLogListRead,
    AuditLogResource,
)
from app.services.audit_logs import REDACTED, list_audit_logs, redact_audit_metadata


class AuthSession:
    def __init__(self, user: User | None) -> None:
        self.user = user

    async def get(self, _model: object, _key: object) -> User | None:
        return self.user


class EmptyResult:
    def all(self) -> list[object]:
        return []


class QuerySession:
    def __init__(self) -> None:
        self.list_statement: object | None = None

    async def scalar(self, _statement: object) -> int:
        return 123

    async def execute(self, statement: object) -> EmptyResult:
        self.list_statement = statement
        return EmptyResult()

    async def scalars(self, _statement: object) -> EmptyResult:
        return EmptyResult()


def user(*, superuser: bool = False, roles: list[str] | None = None) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4()}@example.org",
        first_name="Erika",
        last_name="Muster",
        is_active=True,
        is_verified=True,
        is_superuser=superuser,
        roles=roles or [],
        created_at=now,
        updated_at=now,
    )


def access_cookie(actor: User | None) -> dict[str, str]:
    if not actor:
        return {}
    token, _ = create_jwt(
        str(actor.id), "access", timedelta(minutes=5), {"email": actor.email, "role": "user"}
    )
    return {"ocm_access_token": token}


def empty_page() -> AuditLogListRead:
    return AuditLogListRead(
        items=[], total=0, page=1, page_size=50, pages=1, available_actions=[]
    )


async def audit_request(
    actor: User | None,
    monkeypatch: pytest.MonkeyPatch,
    query: str = "",
) -> tuple[httpx.Response, dict[str, object]]:
    captured: dict[str, object] = {}

    async def override_session():
        yield AuthSession(actor)

    async def fake_list(_session: object, **kwargs: object) -> AuditLogListRead:
        captured.update(kwargs)
        return empty_page()

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(admin_api, "list_audit_logs", fake_list)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=access_cookie(actor),
        ) as client:
            response = await client.get(f"/api/v1/admin/audit-logs{query}")
    finally:
        app.dependency_overrides.clear()
    return response, captured


@pytest.mark.asyncio
async def test_audit_log_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    response, _ = await audit_request(None, monkeypatch)
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("roles", [[], ["VERWALTUNG"]])
async def test_audit_log_rejects_non_superusers(
    roles: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    response, _ = await audit_request(user(roles=roles), monkeypatch)
    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "SUPERUSER_REQUIRED"


@pytest.mark.asyncio
async def test_superuser_can_filter_and_paginate_audit_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    response, captured = await audit_request(
        user(superuser=True),
        monkeypatch,
        "?page=2&page_size=25&action=USER_ACTIVATED"
        f"&user_id={actor_id}&resource_type=USER&resource_id={resource_id}"
        "&date_from=2026-08-01T00:00:00%2B02:00"
        "&date_to=2026-08-16T23:59:59%2B02:00&search=Erika",
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert captured["page"] == 2
    assert captured["page_size"] == 25
    assert captured["action"] == "USER_ACTIVATED"
    assert captured["user_id"] == actor_id
    assert captured["resource_type"] == "USER"
    assert captured["resource_id"] == resource_id
    assert captured["search"] == "Erika"
    assert captured["date_from"] == datetime(2026, 8, 1, tzinfo=UTC) - timedelta(hours=2)


@pytest.mark.asyncio
async def test_audit_log_rejects_invalid_date_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    response, captured = await audit_request(
        user(superuser=True),
        monkeypatch,
        "?date_from=2026-08-17T00:00:00Z&date_to=2026-08-16T00:00:00Z",
    )
    assert response.status_code == 422
    assert not captured


def test_recursive_audit_metadata_redaction() -> None:
    result = redact_audit_metadata(
        {
            "changes": {
                "display_name": {"before": "Alt", "after": "Neu"},
                "password_hash": {"before": "old-hash", "after": "new-hash"},
            },
            "request": [
                {"authorization": "Bearer secret", "safe": True},
                {"refresh_token": "secret-token"},
            ],
        }
    )
    assert result["changes"]["display_name"] == {"before": "Alt", "after": "Neu"}
    assert result["changes"]["password_hash"] == REDACTED
    assert result["request"][0] == {"authorization": REDACTED, "safe": True}
    assert result["request"][1]["refresh_token"] == REDACTED
    assert "secret" not in str(result).lower()


@pytest.mark.asyncio
async def test_audit_query_is_limited_paginated_and_newest_first() -> None:
    session = QuerySession()
    result = await list_audit_logs(
        session,  # type: ignore[arg-type]
        page=3,
        page_size=25,
        action=None,
        user_id=None,
        resource_type=None,
        resource_id=None,
        date_from=None,
        date_to=None,
        search=None,
    )
    sql = str(session.list_statement)
    assert "admin_audit_logs.created_at DESC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert result.total == 123
    assert result.page == 3
    assert result.page_size == 25
    assert result.pages == 5


def test_audit_response_contract_contains_no_authentication_material() -> None:
    item = AuditLogListItem(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        action="USER_ROLE_ASSIGNED",
        actor=AuditLogActor(id=uuid.uuid4(), display_name="Admin", email="admin@example.org"),
        resource=AuditLogResource(type="USER", id=uuid.uuid4(), label="Erika Muster"),
        summary="Rolle wurde zugewiesen.",
        details=redact_audit_metadata({"role": "VERWALTUNG", "access_token": "never-return"}),
    )
    serialized = item.model_dump_json()
    assert "never-return" not in serialized
    assert REDACTED in serialized


def test_openapi_documents_protected_audit_endpoint() -> None:
    operation = app.openapi()["paths"]["/api/v1/admin/audit-logs"]["get"]
    assert "Administration" in operation["tags"]
    assert {"401", "403", "422"}.issubset(operation["responses"])
    assert operation["security"]

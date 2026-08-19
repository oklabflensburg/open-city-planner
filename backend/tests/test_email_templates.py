import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

import app.api.admin as admin_api
import app.services.admin_email_templates as admin_email_service
from app.api.admin import email_template_error
from app.auth.jwt import create_jwt
from app.db.session import get_session
from app.main import app
from app.models.admin_audit_log import AdminAuditLog
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.services.admin_email_templates import (
    EmailTemplateVersionConflict,
    preview_variables,
    reset_email_template,
    send_test_email,
    update_email_template,
)
from app.services.email_service import (
    EMAIL_TEMPLATE_REGISTRY,
    EmailTemplateValidationError,
    render_email_template,
    sanitize_email_html,
    validate_template_content,
)


def actor() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email="admin@example.org",
        first_name="Ada",
        last_name="Admin",
        display_name="Ada Admin",
        is_active=True,
        is_verified=True,
        is_superuser=True,
        roles=[],
        created_at=now,
        updated_at=now,
    )


class AuthSession:
    def __init__(self, user: User | None, *, mfa_configured: bool = True) -> None:
        self.user = user
        self.mfa_configured = mfa_configured

    async def get(self, _model: object, _key: object) -> User | None:
        return self.user

    async def scalar(self, _statement: object) -> object | None:
        return uuid.uuid4() if self.mfa_configured else None


async def admin_template_request(
    user: User | None,
    monkeypatch: pytest.MonkeyPatch,
    *,
    method: str = "GET",
    csrf: bool = True,
    path: str = "/api/v1/admin/email-templates",
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def override_session():
        yield AuthSession(user)

    async def empty_list(_session: object) -> list[object]:
        return []

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(admin_api, "list_email_templates", empty_list)
    cookies = {"ocm_csrf_token": "csrf-token"}
    headers = {"x-csrf-token": "csrf-token"} if csrf else {}
    if user:
        token, _ = create_jwt(
            str(user.id), "access", timedelta(minutes=5), {"amr": ["pwd", "otp"]}
        )
        cookies["ocm_access_token"] = token
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
        ) as client:
            return await client.request(
                method,
                path,
                headers=headers,
                json=json,
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_template_list_is_superuser_only_and_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unauthenticated = await admin_template_request(None, monkeypatch)
    normal = actor()
    normal.is_superuser = False
    forbidden = await admin_template_request(normal, monkeypatch)
    allowed = await admin_template_request(actor(), monkeypatch)

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["error"]["code"] == "SUPERUSER_REQUIRED"
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_admin_template_mutation_requires_csrf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = await admin_template_request(
        actor(),
        monkeypatch,
        method="PATCH",
        csrf=False,
        path="/api/v1/admin/email-templates/password_changed",
        json={
            "subject": "Betreff",
            "html_body": "<p>Hallo {{ name }}</p>",
            "text_body": "Hallo {{ name }}",
            "version": 0,
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "CSRF_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("key", list(EMAIL_TEMPLATE_REGISTRY))
async def test_every_registered_template_has_global_branding_and_legal_links(key: str) -> None:
    rendered = await render_email_template(None, key, preview_variables(key))

    assert "/branding/ok-lab-flensburg-email.png" in rendered.html
    assert 'href="http://localhost:3000/impressum"' in rendered.html
    assert 'href="http://localhost:3000/datenschutz"' in rendered.html
    assert 'href="/impressum"' not in rendered.html
    assert 'href="/datenschutz"' not in rendered.html
    assert "http://localhost:3000/impressum" in rendered.text
    assert "http://localhost:3000/datenschutz" in rendered.text


@pytest.mark.asyncio
async def test_database_override_is_used_and_default_is_fallback() -> None:
    record = SimpleNamespace(
        subject="Eigener Betreff",
        html_body="<p>Hallo {{ name }}</p>",
        text_body="Hallo {{ name }}",
        is_customized=True,
        version=3,
    )
    session = AsyncMock()
    session.scalar.return_value = record

    overridden = await render_email_template(
        session, "password_changed", {"name": "Erika"}
    )
    fallback = await render_email_template(
        None, "password_changed", {"name": "Erika"}
    )

    assert overridden.subject == "Eigener Betreff"
    assert "Hallo Erika" in overridden.html
    assert fallback.subject == "Passwort geändert – OK Lab Flensburg"


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("{{ unbekannt }}", "EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED"),
        ("{{ name.__class__ }}", "EMAIL_TEMPLATE_EXPRESSION_NOT_ALLOWED"),
        ("{{ name.upper() }}", "EMAIL_TEMPLATE_EXPRESSION_NOT_ALLOWED"),
    ],
)
def test_sandbox_rejects_unknown_or_powerful_expressions(value: str, code: str) -> None:
    definition = EMAIL_TEMPLATE_REGISTRY["password_changed"]
    with pytest.raises(EmailTemplateValidationError) as exc_info:
        validate_template_content(definition, "Betreff", f"<p>{value}</p>", value)
    assert exc_info.value.code == code


def test_html_sanitization_removes_active_content_and_unsafe_links() -> None:
    sanitized = sanitize_email_html(
        '<script>alert(1)</script><p onclick="steal()">Text</p>'
        '<a href="javascript:steal()">Link</a><iframe src="https://evil.invalid">x</iframe>'
    )
    assert "script" not in sanitized
    assert "alert" not in sanitized
    assert "onclick" not in sanitized
    assert "javascript:" not in sanitized
    assert "iframe" not in sanitized


def test_subject_header_injection_and_required_security_url_are_rejected() -> None:
    definition = EMAIL_TEMPLATE_REGISTRY["password_reset"]
    with pytest.raises(EmailTemplateValidationError) as header_error:
        validate_template_content(
            definition,
            "Betreff\r\nBcc: victim@example.org",
            definition.default_html,
            definition.default_text,
        )
    assert header_error.value.code == "EMAIL_TEMPLATE_SUBJECT_INVALID"

    with pytest.raises(EmailTemplateValidationError) as link_error:
        validate_template_content(
            definition,
            definition.default_subject,
            "<p>Kein Aktionslink</p>",
            "Kein Aktionslink",
        )
    assert link_error.value.code == "EMAIL_TEMPLATE_REQUIRED_VARIABLE_MISSING"


@pytest.mark.asyncio
async def test_update_is_versioned_and_audited_without_template_body() -> None:
    admin = actor()
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = None

    result = await update_email_template(
        session,
        "password_changed",
        subject="Neuer Betreff",
        html_body="<p>Hallo {{ name }}</p>",
        text_body="Hallo {{ name }}",
        expected_version=0,
        actor=admin,
    )

    assert result.version == 1
    assert result.customized is True
    audits = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], AdminAuditLog)
    ]
    assert audits[0].action == "EMAIL_TEMPLATE_UPDATED"
    assert "<p>Hallo" not in str(audits[0].event_metadata.values())


@pytest.mark.asyncio
async def test_concurrent_update_is_rejected() -> None:
    record = SimpleNamespace(version=4)
    session = AsyncMock()
    session.scalar.return_value = record
    with pytest.raises(EmailTemplateVersionConflict):
        await update_email_template(
            session,
            "password_changed",
            subject="Betreff",
            html_body="<p>Hallo {{ name }}</p>",
            text_body="Hallo {{ name }}",
            expected_version=3,
            actor=actor(),
        )


@pytest.mark.asyncio
async def test_reset_restores_repository_default() -> None:
    definition = EMAIL_TEMPLATE_REGISTRY["password_changed"]
    record = EmailTemplate(
        id=uuid.uuid4(),
        key="password_changed",
        subject="Geändert",
        html_body="<p>Geändert</p>",
        text_body="Geändert",
        is_customized=True,
        version=2,
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = record

    result = await reset_email_template(
        session, "password_changed", expected_version=2, actor=actor()
    )

    assert result.subject == definition.default_subject
    assert result.customized is False
    assert result.version == 3


@pytest.mark.asyncio
async def test_test_send_targets_only_the_current_superuser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = actor()
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.return_value = None
    deliver = AsyncMock()
    monkeypatch.setattr(admin_email_service, "send_rendered_email", deliver)
    definition = EMAIL_TEMPLATE_REGISTRY["password_changed"]

    await send_test_email(
        session,
        "password_changed",
        subject=definition.default_subject,
        html_body=definition.default_html,
        text_body=definition.default_text,
        version=0,
        actor=admin,
    )

    deliver.assert_awaited_once()
    assert deliver.await_args.args[0] == admin.email
    audits = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], AdminAuditLog)
    ]
    assert audits[0].action == "EMAIL_TEMPLATE_TEST_SENT"


def test_validation_errors_keep_stable_api_codes() -> None:
    response: HTTPException = email_template_error(
        EmailTemplateValidationError(
            "EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED",
            "Nicht erlaubt.",
            variable="foo",
        )
    )
    assert response.status_code == 422
    assert response.detail["error"]["code"] == "EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED"
    assert response.detail["error"]["variable"] == "foo"

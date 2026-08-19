import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.email_outbox as outbox_service
import app.services.oauth_account_service as oauth_service
from app.models.email_outbox import EmailOutbox
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.models.verification_token import EmailVerificationToken
from app.schemas.auth import SignupRequest
from app.schemas.oauth import OAuthIdentity
from app.services import auth_service
from app.services.email_service import EMAIL_TEMPLATE_REGISTRY, render_email_template


@pytest.mark.asyncio
async def test_signup_sends_no_welcome_email(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    monkeypatch.setattr(auth_service, "get_user_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(auth_service, "hash_password", lambda _password: "password-hash")
    monkeypatch.setattr(auth_service, "create_verification_token", AsyncMock(return_value="token"))
    verification = AsyncMock()
    monkeypatch.setattr(auth_service, "send_verification_email", verification)

    user = await auth_service.signup(
        session,
        SignupRequest(
            email="neu@example.org",
            password="ein-sehr-sicheres-passwort",
            first_name="Max",
            last_name="Mustermann",
        ),
    )

    assert user.is_verified is False
    assert not any(isinstance(call.args[0], EmailOutbox) for call in session.add.call_args_list)
    verification.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_verified_oauth_user_enqueues_welcome_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = oauth_service_test_session()
    monkeypatch.setattr(oauth_service, "get_by_provider_subject", AsyncMock(return_value=None))
    monkeypatch.setattr(oauth_service, "get_user_by_email", AsyncMock(return_value=None))

    user = await oauth_service.authenticate_oauth_identity(
        session,
        OAuthIdentity(
            provider="google",
            subject="oauth-user",
            email="oauth@example.org",
            email_verified=True,
            display_name="OAuth Nutzer",
        ),
    )

    assert user.is_verified is True
    assert len([item for item in session.added if isinstance(item, EmailOutbox)]) == 1


@pytest.mark.asyncio
async def test_new_unverified_oauth_user_enqueues_no_welcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = oauth_service_test_session()
    monkeypatch.setattr(oauth_service, "get_by_provider_subject", AsyncMock(return_value=None))
    monkeypatch.setattr(oauth_service, "get_user_by_email", AsyncMock(return_value=None))

    user = await oauth_service.authenticate_oauth_identity(
        session,
        OAuthIdentity(
            provider="github",
            subject="oauth-user",
            email="oauth@example.org",
            email_verified=False,
        ),
    )

    assert user.is_verified is False
    assert not any(isinstance(item, EmailOutbox) for item in session.added)


@pytest.mark.asyncio
async def test_pending_oauth_user_is_enqueued_after_later_email_verification() -> None:
    user = User(
        id=uuid.uuid4(),
        email="nachgereicht@example.org",
        email_pending=False,
        is_verified=False,
    )
    token = EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.side_effect = [token, user]

    result = await auth_service.verify_email(session, "nachgereichter-token")

    assert result.changed_user_state is True
    assert user.is_verified is True
    assert sum(isinstance(call.args[0], EmailOutbox) for call in session.add.call_args_list) == 1


@pytest.mark.asyncio
async def test_smtp_failure_keeps_verified_user_and_event_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = verified_user()
    event = EmailOutbox(
        id=uuid.uuid4(),
        template_key="welcome",
        user_id=user.id,
        status="PROCESSING",
        attempt_count=1,
        scheduled_at=datetime.now(UTC),
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.side_effect = [event, user, event]
    monkeypatch.setattr(
        outbox_service,
        "send_welcome_email",
        AsyncMock(side_effect=RuntimeError("SMTP vorübergehend nicht erreichbar")),
    )

    sent = await outbox_service._finish_welcome_event(session, event.id)

    assert sent is False
    assert user.is_verified is True
    assert user.welcome_email_sent_at is None
    assert event.status == "PENDING"
    assert event.scheduled_at > datetime.now(UTC)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_successful_delivery_marks_user_and_outbox_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = verified_user()
    event = EmailOutbox(
        id=uuid.uuid4(),
        template_key="welcome",
        user_id=user.id,
        status="PROCESSING",
        attempt_count=1,
        scheduled_at=datetime.now(UTC),
    )
    session = AsyncMock()
    session.add = MagicMock()
    session.scalar.side_effect = [event, user]
    sender = AsyncMock()
    monkeypatch.setattr(outbox_service, "send_welcome_email", sender)

    assert await outbox_service._finish_welcome_event(session, event.id) is True

    sender.assert_awaited_once_with(session, user)
    assert event.status == "SENT"
    assert event.sent_at is not None
    assert user.welcome_email_sent_at == event.sent_at


@pytest.mark.asyncio
async def test_welcome_template_is_active_and_uses_database_override() -> None:
    definition = EMAIL_TEMPLATE_REGISTRY["welcome"]
    assert definition.is_active is True
    assert {"name", "app_url", "documentation_url"} <= definition.allowed_variables

    record = EmailTemplate(
        key="welcome",
        subject="Eigener Willkommensbetreff",
        html_body=(
            '<p>Hallo {{ name }}</p><p><a href="{{ app_url }}">Start</a></p>'
            '<p><a href="{{ documentation_url }}">Hilfe</a></p>'
        ),
        text_body=("Hallo {{ name }}\n{{ app_url }}\n{{ documentation_url }}"),
        is_customized=True,
        version=2,
    )
    session = AsyncMock()
    session.scalar.return_value = record

    rendered = await render_email_template(
        session,
        "welcome",
        {
            "name": "Max Mustermann",
            "app_url": "https://example.invalid",
            "documentation_url": "https://example.invalid/dokumentation",
        },
    )

    assert rendered.subject == "Eigener Willkommensbetreff"
    assert "ok-lab-flensburg-email.png" in rendered.html
    assert "/impressum" in rendered.html and "/datenschutz" in rendered.html
    assert "Impressum:" in rendered.text and "Datenschutz:" in rendered.text


@pytest.mark.asyncio
async def test_welcome_template_falls_back_to_registry_default() -> None:
    rendered = await render_email_template(
        None,
        "welcome",
        {
            "name": "Max Mustermann",
            "app_url": "https://example.invalid",
            "documentation_url": "https://example.invalid/dokumentation",
            "profile_url": "https://example.invalid/profil",
        },
    )

    assert rendered.subject == "Willkommen beim Stadtplaner – OK Lab Flensburg"
    assert "offene Geodaten" in rendered.text
    assert "https://example.invalid/dokumentation" in rendered.html


class OAuthTestSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        for item in self.added:
            if isinstance(item, User) and item.id is None:
                item.id = uuid.uuid4()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, _item: object) -> None:
        return None


def oauth_service_test_session() -> OAuthTestSession:
    return OAuthTestSession()


def verified_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="user@example.org",
        display_name="Max Mustermann",
        is_verified=True,
    )


def test_outbox_uses_generic_unique_idempotency_key() -> None:
    assert EmailOutbox.__table__.c.idempotency_key.unique is True

import asyncio
from email.message import EmailMessage
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

import app.api.contact as contact_api
from app.core.config import get_settings
from app.main import app
from app.schemas.contact import ContactMessageCreate
from app.services import contact_service, email_service, rate_limit


def valid_payload(token: str, **changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Erika Beispiel",
        "email": "erika@example.org",
        "subject": "Hinweis zur Karte",
        "message": "Ich habe einen hilfreichen Hinweis zu einer Fläche auf der Karte.",
        "website": "",
        "form_token": token,
        "turnstile_token": None,
    }
    payload.update(changes)
    return payload


@pytest.fixture(autouse=True)
def contact_state(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "contact_to_email", "kontakt@example.org")
    monkeypatch.setattr(settings, "contact_form_min_seconds", 0)
    monkeypatch.setattr(settings, "contact_ip_rate_limit_attempts", 20)
    monkeypatch.setattr(settings, "contact_email_rate_limit_attempts", 20)
    monkeypatch.setattr(settings, "contact_turnstile_enabled", False)
    rate_limit.reset_memory_rate_limits()
    contact_service._used_nonces.clear()
    contact_service._pending_nonces.clear()


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"name": "A"}, "name"),
        ({"email": "keine-mail"}, "email"),
        ({"subject": "x" * 161}, "subject"),
        ({"message": "x" * 5001}, "message"),
    ],
)
def test_contact_schema_rejects_invalid_fields(changes: dict[str, object], field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ContactMessageCreate(**valid_payload("a" * 20, **changes))
    assert field in str(exc.value)


def test_contact_schema_normalizes_and_rejects_header_injection() -> None:
    payload = ContactMessageCreate(
        **valid_payload("a" * 20, name="  Erika Beispiel  ", email=" ERIKA@EXAMPLE.ORG ")
    )
    assert payload.name == "Erika Beispiel"
    assert str(payload.email) == "erika@example.org"
    with pytest.raises(ValidationError):
        ContactMessageCreate(**valid_payload("a" * 20, subject="Hallo\nBcc: victim@example.org"))


async def post_contact(
    monkeypatch: pytest.MonkeyPatch,
    *,
    changes: dict[str, object] | None = None,
    origin: str = "http://localhost:3000",
    notification: AsyncMock | None = None,
    copy: AsyncMock | None = None,
) -> tuple[httpx.Response, AsyncMock, AsyncMock]:
    notification = notification or AsyncMock()
    copy = copy or AsyncMock()
    monkeypatch.setattr(contact_api, "send_contact_notification", notification)
    monkeypatch.setattr(contact_api, "send_contact_copy", copy)
    token = contact_service.create_form_token()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/contact",
            json=valid_payload(token, **(changes or {})),
            headers={"Origin": origin},
        )
    return response, notification, copy


@pytest.mark.asyncio
async def test_contact_sends_notification_with_reply_data_and_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, notification, copy = await post_contact(monkeypatch)
    assert response.status_code == 200
    assert response.json() == {"status": "sent", "copy_sent": True}
    notification.assert_awaited_once()
    assert notification.call_args.kwargs["email"] == "erika@example.org"
    copy.assert_awaited_once()
    assert copy.call_args.kwargs["message"].startswith("Ich habe")


@pytest.mark.asyncio
async def test_contact_form_token_endpoint_exposes_no_secret() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/contact/form-token")
    assert response.status_code == 200
    assert response.json()["form_token"]
    assert "secret" not in response.json()


@pytest.mark.asyncio
async def test_api_validation_uses_stable_contact_error_code() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/contact",
            json=valid_payload(contact_service.create_form_token(), email="invalid"),
            headers={"Origin": "http://localhost:3000"},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "CONTACT_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_honeypot_returns_neutral_success_without_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, notification, copy = await post_contact(
        monkeypatch, changes={"website": "https://spam.invalid"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    notification.assert_not_called()
    copy.assert_not_called()


@pytest.mark.asyncio
async def test_wrong_origin_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    response, notification, _copy = await post_contact(monkeypatch, origin="https://evil.example")
    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "CONTACT_FORM_TOKEN_INVALID"
    notification.assert_not_called()


@pytest.mark.asyncio
async def test_too_fast_submission_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "contact_form_min_seconds", 30)
    response, notification, _copy = await post_contact(monkeypatch)
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "CONTACT_SPAM_REJECTED"
    notification.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_uses_contact_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "contact_ip_rate_limit_attempts", 1)
    first, _, _ = await post_contact(monkeypatch)
    second, notification, _ = await post_contact(monkeypatch)
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["error"]["code"] == "CONTACT_RATE_LIMITED"
    notification.assert_not_called()


@pytest.mark.asyncio
async def test_spam_heuristic_rejects_many_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    message = " ".join(f"https://example.org/{index}" for index in range(8))
    response, notification, _copy = await post_contact(monkeypatch, changes={"message": message})
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "CONTACT_SPAM_REJECTED"
    notification.assert_not_called()


@pytest.mark.asyncio
async def test_copy_failure_does_not_fail_delivered_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, notification, _copy = await post_contact(
        monkeypatch, copy=AsyncMock(side_effect=RuntimeError("mail error"))
    )
    assert response.status_code == 200
    assert response.json()["copy_sent"] is False
    notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_notification_failure_returns_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    response, _notification, copy = await post_contact(
        monkeypatch, notification=AsyncMock(side_effect=RuntimeError("SMTP secret detail"))
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "CONTACT_SEND_FAILED"
    assert "SMTP" not in response.text
    copy.assert_not_called()


@pytest.mark.asyncio
async def test_parallel_replay_sends_operator_mail_once(monkeypatch: pytest.MonkeyPatch) -> None:
    notification = AsyncMock()
    copy = AsyncMock()
    monkeypatch.setattr(contact_api, "send_contact_notification", notification)
    monkeypatch.setattr(contact_api, "send_contact_copy", copy)
    token = contact_service.create_form_token()

    async def submit() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/api/v1/contact",
                json=valid_payload(token),
                headers={"Origin": "http://localhost:3000"},
            )

    responses = await asyncio.gather(submit(), submit())
    assert sorted(response.status_code for response in responses) == [200, 409]
    notification.assert_awaited_once()


def test_contact_templates_escape_user_html() -> None:
    html, text = email_service.render_pair(
        "contact_notification",
        {
            "name": "<script>alert(1)</script>",
            "email": "a@example.org",
            "subject": "Test",
            "message": "<b>nicht fett</b>",
            "received_at": "heute",
        },
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>nicht fett</b>" not in html
    assert "<b>nicht fett</b>" in text


def test_smtp_message_keeps_system_from_and_sets_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.org")
    monkeypatch.setattr(settings, "smtp_from_email", "noreply@example.org")
    sent: list[EmailMessage] = []

    class FakeSMTP:
        def __init__(self, _host: str, _port: int) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def starttls(self) -> None:
            pass

        def login(self, _username: str, _password: str) -> None:
            pass

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    email_service.send_email(
        "kontakt@example.org", "Test", "<p>Text</p>", "Text", reply_to="user@example.org"
    )
    assert sent[0]["From"].addresses[0].addr_spec == "noreply@example.org"  # type: ignore[union-attr]
    assert sent[0]["Reply-To"].addresses[0].addr_spec == "user@example.org"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_turnstile_is_optional_and_invalid_response_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await contact_service.verify_turnstile(None, "127.0.0.1")
    settings = get_settings()
    monkeypatch.setattr(settings, "contact_turnstile_enabled", True)
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    with pytest.raises(Exception) as exc:
        await contact_service.verify_turnstile(None, "127.0.0.1")
    assert exc.value.detail["error"]["code"] == "CONTACT_SPAM_REJECTED"


@pytest.mark.asyncio
async def test_turnstile_accepts_mocked_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "contact_turnstile_enabled", True)
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")

    class Response:
        def json(self) -> dict[str, bool]:
            return {"success": True}

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        async def post(self, _url: str, **_kwargs: object) -> Response:
            return Response()

    monkeypatch.setattr(contact_service.httpx, "AsyncClient", Client)
    await contact_service.verify_turnstile("valid-token", "127.0.0.1")

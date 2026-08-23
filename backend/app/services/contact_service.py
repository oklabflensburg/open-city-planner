import asyncio
import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.observability.external import instrumented_httpx_request
from app.schemas.contact import ContactMessageCreate

logger = logging.getLogger(__name__)
_used_nonces: dict[str, datetime] = {}
_pending_nonces: set[str] = set()
_nonce_lock = asyncio.Lock()
_url_pattern = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)


def contact_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def create_form_token() -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "purpose": "contact_form",
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.contact_form_token_expire_minutes)).timestamp()
        ),
        "nonce": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_form_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise contact_error(
            status.HTTP_403_FORBIDDEN,
            "CONTACT_FORM_TOKEN_INVALID",
            "Das Kontaktformular ist abgelaufen. Bitte laden Sie die Seite neu.",
        ) from exc
    if payload.get("purpose") != "contact_form" or not payload.get("nonce"):
        raise contact_error(
            status.HTTP_403_FORBIDDEN,
            "CONTACT_FORM_TOKEN_INVALID",
            "Das Kontaktformular ist ungültig. Bitte laden Sie die Seite neu.",
        )
    issued_at = datetime.fromtimestamp(int(payload.get("iat", 0)), UTC)
    if datetime.now(UTC) - issued_at < timedelta(seconds=settings.contact_form_min_seconds):
        raise contact_error(
            status.HTTP_400_BAD_REQUEST,
            "CONTACT_SPAM_REJECTED",
            "Bitte prüfen Sie Ihre Angaben und versuchen Sie es gleich noch einmal.",
        )
    return payload


def validate_contact_origin(request: Request) -> None:
    settings = get_settings()
    origin = (request.headers.get("origin") or "").rstrip("/")
    allowed = set(settings.cors_origin_list)
    allowed.add(settings.app_base_url.rstrip("/"))
    regex_allowed = bool(
        origin and settings.cors_origin_regex and re.fullmatch(settings.cors_origin_regex, origin)
    )
    if not origin or (origin not in allowed and not regex_allowed):
        logger.warning("Contact request rejected due to invalid origin")
        raise contact_error(
            status.HTTP_403_FORBIDDEN,
            "CONTACT_FORM_TOKEN_INVALID",
            "Die Sicherheitsprüfung ist fehlgeschlagen.",
        )


def spam_rejection_reason(payload: ContactMessageCreate) -> str | None:
    combined = f"{payload.subject}\n{payload.message}"
    if any(ord(char) < 32 and char not in "\n\r\t" for char in combined):
        return "control_characters"
    if len(_url_pattern.findall(combined)) > 7:
        return "too_many_urls"
    if re.search(r"(.)\1{29,}", combined, re.DOTALL):
        return "excessive_character_repetition"
    words = re.findall(r"\w+", payload.message.lower())
    if len(words) >= 30 and len(set(words)) <= max(2, len(words) // 10):
        return "excessive_word_repetition"
    return None


async def reserve_nonce(nonce: str) -> None:
    now = datetime.now(UTC)
    settings = get_settings()
    cutoff = now - timedelta(minutes=settings.contact_form_token_expire_minutes)
    async with _nonce_lock:
        for key, used_at in list(_used_nonces.items()):
            if used_at < cutoff:
                del _used_nonces[key]
        if nonce in _used_nonces or nonce in _pending_nonces:
            raise contact_error(
                status.HTTP_409_CONFLICT,
                "CONTACT_FORM_TOKEN_INVALID",
                "Dieses Formular wurde bereits gesendet. Bitte laden Sie die Seite neu.",
            )
        _pending_nonces.add(nonce)


async def finish_nonce(nonce: str, *, sent: bool) -> None:
    async with _nonce_lock:
        _pending_nonces.discard(nonce)
        if sent:
            _used_nonces[nonce] = datetime.now(UTC)


async def verify_turnstile(token: str | None, remote_ip: str) -> None:
    settings = get_settings()
    if not settings.contact_turnstile_enabled:
        return
    if not token or not settings.turnstile_secret_key:
        raise contact_error(
            status.HTTP_400_BAD_REQUEST,
            "CONTACT_SPAM_REJECTED",
            "Bitte bestätigen Sie die Sicherheitsprüfung.",
        )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await instrumented_httpx_request(
                client,
                "POST",
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                provider="cloudflare_turnstile",
                operation="verify",
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": remote_ip,
                },
            )
            valid = bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError):
        logger.exception("Turnstile verification failed")
        raise contact_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CONTACT_SEND_FAILED",
            "Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es später erneut.",
        ) from None
    if not valid:
        raise contact_error(
            status.HTTP_400_BAD_REQUEST,
            "CONTACT_SPAM_REJECTED",
            "Die Sicherheitsprüfung war nicht erfolgreich.",
        )


def masked_email_hash(email: str) -> str:
    return hashlib.sha256(email.lower().encode()).hexdigest()[:12]

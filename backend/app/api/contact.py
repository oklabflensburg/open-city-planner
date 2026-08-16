import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.schemas.contact import (
    ContactFormTokenResponse,
    ContactMessageCreate,
    ContactMessageResponse,
)
from app.services.contact_service import (
    contact_error,
    create_form_token,
    decode_form_token,
    finish_nonce,
    masked_email_hash,
    reserve_nonce,
    spam_rejection_reason,
    validate_contact_origin,
    verify_turnstile,
)
from app.services.email_service import send_contact_copy, send_contact_notification
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/contact", tags=["Contact"])
logger = logging.getLogger(__name__)


@router.get("/form-token", response_model=ContactFormTokenResponse)
async def get_contact_form_token() -> ContactFormTokenResponse:
    settings = get_settings()
    return ContactFormTokenResponse(
        form_token=create_form_token(),
        turnstile_enabled=settings.contact_turnstile_enabled,
        turnstile_site_key=(
            settings.turnstile_site_key if settings.contact_turnstile_enabled else None
        ),
    )


@router.post("", response_model=ContactMessageResponse)
async def post_contact_message(
    payload: ContactMessageCreate,
    request: Request,
) -> ContactMessageResponse:
    settings = get_settings()
    request_id = str(uuid.uuid4())
    remote_ip = request.client.host if request.client else "unknown"
    email_hash = masked_email_hash(str(payload.email))
    validate_contact_origin(request)
    try:
        check_rate_limit(
            f"contact-ip:{remote_ip}",
            attempts=settings.contact_ip_rate_limit_attempts,
            window_seconds=settings.contact_rate_limit_window_seconds,
            code="CONTACT_RATE_LIMITED",
            message="Zu viele Nachrichten in kurzer Zeit. Bitte versuchen Sie es später erneut.",
        )
        check_rate_limit(
            f"contact-email:{email_hash}",
            attempts=settings.contact_email_rate_limit_attempts,
            window_seconds=settings.contact_rate_limit_window_seconds,
            code="CONTACT_RATE_LIMITED",
            message="Zu viele Nachrichten in kurzer Zeit. Bitte versuchen Sie es später erneut.",
        )
    except Exception:
        logger.warning(
            "Contact rate limit reached request_id=%s email_hash=%s",
            request_id,
            email_hash,
        )
        raise

    token_payload = decode_form_token(payload.form_token)
    nonce = str(token_payload["nonce"])
    await reserve_nonce(nonce)

    if payload.website:
        logger.info("Contact spam rejected request_id=%s reason=honeypot", request_id)
        await finish_nonce(nonce, sent=True)
        return ContactMessageResponse(copy_sent=True)

    rejection_reason = spam_rejection_reason(payload)
    if rejection_reason:
        logger.info(
            "Contact spam rejected request_id=%s reason=%s",
            request_id,
            rejection_reason,
        )
        await finish_nonce(nonce, sent=True)
        raise contact_error(
            status.HTTP_400_BAD_REQUEST,
            "CONTACT_SPAM_REJECTED",
            "Die Nachricht konnte nicht verarbeitet werden. Bitte prüfen Sie Ihre Angaben.",
        )

    try:
        await verify_turnstile(payload.turnstile_token, remote_ip)
        await run_in_threadpool(
            send_contact_notification,
            name=payload.name,
            email=str(payload.email),
            subject=payload.subject,
            message=payload.message,
            received_at=datetime.now(UTC).astimezone().strftime("%d.%m.%Y, %H:%M %Z"),
        )
    except Exception as exc:
        await finish_nonce(nonce, sent=False)
        if hasattr(exc, "status_code"):
            raise
        logger.exception(
            "Contact notification failed request_id=%s email_hash=%s",
            request_id,
            email_hash,
        )
        raise contact_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CONTACT_SEND_FAILED",
            "Die Nachricht konnte nicht gesendet werden. Bitte versuchen Sie es später erneut.",
        ) from None

    await finish_nonce(nonce, sent=True)
    copy_sent = True
    try:
        await run_in_threadpool(
            send_contact_copy,
            name=payload.name,
            email=str(payload.email),
            subject=payload.subject,
            message=payload.message,
        )
    except Exception:
        copy_sent = False
        logger.exception(
            "Contact copy failed request_id=%s email_hash=%s",
            request_id,
            email_hash,
        )
    logger.info(
        "Contact notification sent request_id=%s email_hash=%s copy_sent=%s",
        request_id,
        email_hash,
        copy_sent,
    )
    return ContactMessageResponse(copy_sent=copy_sent)

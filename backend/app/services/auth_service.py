import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import create_csrf_token
from app.auth.jwt import create_jwt, decode_jwt
from app.auth.passwords import hash_password, validate_password_policy, verify_password
from app.auth.tokens import generate_token, hash_token
from app.core.config import get_settings
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.models.user_session import UserSession
from app.models.verification_token import EmailVerificationToken
from app.schemas.auth import LoginRequest, SignupRequest
from app.services.email_service import (
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerificationResult:
    status: Literal["verified", "already_verified"]
    changed_user_state: bool


def utcnow() -> datetime:
    return datetime.now(UTC)


def auth_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(func.lower(User.email) == email.lower()))


async def get_user_by_id(session: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    try:
        parsed_id = uuid.UUID(str(user_id))
    except ValueError:
        return None
    return await session.get(User, parsed_id)


async def create_verification_token(session: AsyncSession, user: User) -> str:
    settings = get_settings()
    token = generate_token()
    record = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(hours=settings.email_verification_expire_hours),
    )
    session.add(record)
    await session.commit()
    return token


async def signup(session: AsyncSession, payload: SignupRequest) -> User:
    existing = await get_user_by_email(session, str(payload.email))
    if existing:
        raise auth_error("EMAIL_ALREADY_REGISTERED", "Diese E-Mail-Adresse ist bereits registriert.", status.HTTP_409_CONFLICT)
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise auth_error("INVALID_PASSWORD", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    user = User(
        email=str(payload.email),
        password_hash=password_hash,
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    token = await create_verification_token(session, user)
    send_verification_email(user, token)
    return user


async def authenticate(session: AsyncSession, payload: LoginRequest) -> User:
    user = await get_user_by_email(session, str(payload.email))
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise auth_error("INVALID_CREDENTIALS", "E-Mail-Adresse oder Passwort ist nicht korrekt.", status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        raise auth_error("ACCOUNT_INACTIVE", "Dieses Konto ist deaktiviert.", status.HTTP_403_FORBIDDEN)
    user.last_login_at = utcnow()
    await session.commit()
    await session.refresh(user)
    return user


async def issue_session(session: AsyncSession, response: Response, user: User, request: Request) -> str:
    settings = get_settings()
    access_token, _ = create_jwt(
        str(user.id),
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        {"email": user.email, "role": "superuser" if user.is_superuser else "user"},
    )
    refresh_token, refresh_jti = create_jwt(str(user.id), "refresh", timedelta(days=settings.refresh_token_expire_days))
    session_record = UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        jti=refresh_jti,
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(session_record)
    await session.commit()
    csrf_token = create_csrf_token()
    set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return csrf_token


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    settings = get_settings()
    common = {
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "domain": settings.auth_cookie_domain,
    }
    response.set_cookie(settings.auth_access_cookie_name, access_token, httponly=True, path=settings.auth_cookie_path, max_age=settings.access_token_expire_minutes * 60, **common)
    response.set_cookie(settings.auth_refresh_cookie_name, refresh_token, httponly=True, path="/api/v1/auth", max_age=settings.refresh_token_expire_days * 86400, **common)
    response.set_cookie(settings.auth_csrf_cookie_name, csrf_token, httponly=False, path=settings.auth_cookie_path, max_age=settings.refresh_token_expire_days * 86400, **common)


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name, path in [
        (settings.auth_access_cookie_name, settings.auth_cookie_path),
        (settings.auth_refresh_cookie_name, "/api/v1/auth"),
        (settings.auth_csrf_cookie_name, settings.auth_cookie_path),
    ]:
        response.delete_cookie(name, path=path, domain=settings.auth_cookie_domain)


async def refresh_session(session: AsyncSession, response: Response, refresh_token: str, request: Request) -> tuple[User, str]:
    try:
        payload = decode_jwt(refresh_token, "refresh")
    except jwt.PyJWTError as exc:
        raise auth_error("AUTH_REQUIRED", "Bitte melde dich erneut an.", status.HTTP_401_UNAUTHORIZED) from exc
    user = await get_user_by_id(session, payload["sub"])
    if not user or not user.is_active:
        raise auth_error("AUTH_REQUIRED", "Bitte melde dich erneut an.", status.HTTP_401_UNAUTHORIZED)
    record = await session.scalar(select(UserSession).where(UserSession.jti == payload["jti"]))
    now = utcnow()
    if not record or record.revoked_at or record.expires_at <= now or record.token_hash != hash_token(refresh_token):
        raise auth_error("AUTH_REQUIRED", "Bitte melde dich erneut an.", status.HTTP_401_UNAUTHORIZED)
    record.revoked_at = now
    record.last_used_at = now
    await session.commit()
    csrf_token = await issue_session(session, response, user, request)
    return user, csrf_token


async def revoke_current_session(session: AsyncSession, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        payload = decode_jwt(refresh_token, "refresh")
    except jwt.PyJWTError:
        return
    record = await session.scalar(select(UserSession).where(UserSession.jti == payload["jti"]))
    if record and not record.revoked_at:
        record.revoked_at = utcnow()
        await session.commit()


async def revoke_all_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await session.commit()


async def verify_email(session: AsyncSession, token: str) -> VerificationResult:
    record = await session.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == hash_token(token))
        .with_for_update()
    )
    now = utcnow()
    if not record:
        raise auth_error(
            "VERIFICATION_TOKEN_INVALID",
            "Der Bestätigungslink ist ungültig.",
            status.HTTP_400_BAD_REQUEST,
        )
    user = await session.scalar(
        select(User)
        .where(User.id == record.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user:
        raise auth_error(
            "VERIFICATION_TOKEN_INVALID",
            "Der Bestätigungslink ist ungültig.",
            status.HTTP_400_BAD_REQUEST,
        )
    if user.is_verified:
        await session.commit()
        return VerificationResult(status="already_verified", changed_user_state=False)
    if record.used_at:
        logger.error(
            "Email verification state is inconsistent for token_id=%s user_id=%s",
            record.id,
            user.id,
        )
        raise auth_error(
            "VERIFICATION_STATE_INVALID",
            "Der Bestätigungsstatus des Kontos ist inkonsistent.",
            status.HTTP_409_CONFLICT,
        )
    if record.expires_at <= now:
        raise auth_error(
            "VERIFICATION_TOKEN_EXPIRED",
            "Der Bestätigungslink ist abgelaufen.",
            status.HTTP_400_BAD_REQUEST,
        )
    user.is_verified = True
    record.used_at = now
    await session.commit()
    return VerificationResult(status="verified", changed_user_state=True)


async def resend_verification(session: AsyncSession, user: User) -> bool:
    locked_user = await session.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_user:
        raise auth_error("AUTH_REQUIRED", "Bitte melde dich erneut an.", status.HTTP_401_UNAUTHORIZED)
    if locked_user.is_verified:
        await session.commit()
        return False
    token = await create_verification_token(session, locked_user)
    send_verification_email(locked_user, token)
    return True


async def forgot_password(session: AsyncSession, email: str, request: Request) -> None:
    user = await get_user_by_email(session, email)
    if not user or not user.is_active:
        return
    settings = get_settings()
    token = generate_token()
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(minutes=settings.password_reset_expire_minutes),
        requested_ip=request.client.host if request.client else None,
    )
    session.add(record)
    await session.commit()
    send_password_reset_email(user, token)


async def reset_password(session: AsyncSession, token: str, password: str) -> User:
    try:
        validate_password_policy(password)
    except ValueError as exc:
        raise auth_error("INVALID_PASSWORD", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    record = await session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    now = utcnow()
    if not record or record.used_at:
        raise auth_error("INVALID_RESET_TOKEN", "Der Reset-Link ist ungültig.", status.HTTP_400_BAD_REQUEST)
    if record.expires_at <= now:
        raise auth_error("RESET_TOKEN_EXPIRED", "Der Reset-Link ist abgelaufen.", status.HTTP_400_BAD_REQUEST)
    user = await session.get(User, record.user_id)
    if not user:
        raise auth_error("INVALID_RESET_TOKEN", "Der Reset-Link ist ungültig.", status.HTTP_400_BAD_REQUEST)
    user.password_hash = hash_password(password)
    user.updated_at = now
    record.used_at = now
    await revoke_all_sessions(session, user.id)
    await session.commit()
    send_password_changed_email(user)
    return user


async def change_password(session: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not user.password_hash or not verify_password(current_password, user.password_hash):
        raise auth_error("INVALID_CREDENTIALS", "Das aktuelle Passwort ist nicht korrekt.", status.HTTP_401_UNAUTHORIZED)
    user.password_hash = hash_password(new_password)
    user.updated_at = utcnow()
    await session.commit()
    send_password_changed_email(user)

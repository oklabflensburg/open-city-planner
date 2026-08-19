import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
import pyotp
from fastapi import Request, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_jwt
from app.auth.passwords import verify_password
from app.auth.tokens import generate_token, hash_token
from app.core.config import get_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.mfa import (
    AuthMfaChallenge,
    UserMfaMethod,
    UserMfaRecoveryCode,
    UserWebAuthnCredential,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.security.encryption import MfaEncryptionError, decrypt_mfa_secret, encrypt_mfa_secret
from app.services.auth_service import auth_error, utcnow


@dataclass(frozen=True)
class ChallengeResult:
    token: str
    expires_in: int


def _configuration_error() -> Exception:
    return auth_error(
        "MFA_SECRET_CONFIGURATION_ERROR",
        "Die Zwei-Faktor-Authentifizierung ist serverseitig nicht korrekt konfiguriert.",
        status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _secret_encrypt(secret: str) -> str:
    try:
        return encrypt_mfa_secret(secret)
    except MfaEncryptionError as exc:
        raise _configuration_error() from exc


def _secret_decrypt(ciphertext: str) -> str:
    try:
        return decrypt_mfa_secret(ciphertext)
    except MfaEncryptionError as exc:
        raise _configuration_error() from exc


def normalize_recovery_code(code: str) -> str:
    return "".join(character for character in code.upper() if character.isalnum())


def recovery_code_hash(code: str) -> str:
    normalized = normalize_recovery_code(code)
    key = get_settings().mfa_recovery_pepper.encode()
    return hmac.new(key, normalized.encode(), hashlib.sha256).hexdigest()


def generate_recovery_codes() -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    codes: list[str] = []
    for _ in range(get_settings().mfa_recovery_code_count):
        raw = "".join(secrets.choice(alphabet) for _ in range(12))
        codes.append("-".join((raw[:4], raw[4:8], raw[8:])))
    return codes


async def enabled_method(
    session: AsyncSession, user_id: uuid.UUID, *, lock: bool = False
) -> UserMfaMethod | None:
    query = select(UserMfaMethod).where(
        UserMfaMethod.user_id == user_id,
        UserMfaMethod.type == "totp",
        UserMfaMethod.is_enabled.is_(True),
    )
    if lock:
        query = query.with_for_update()
    return await session.scalar(query)


async def user_requires_mfa(session: AsyncSession, user_id: uuid.UUID) -> bool:
    if await enabled_method(session, user_id) is not None:
        return True
    return bool(
        await session.scalar(
            select(UserWebAuthnCredential.id).where(UserWebAuthnCredential.user_id == user_id)
        )
    )


async def create_login_challenge(
    session: AsyncSession,
    user: User,
    request: Request,
    *,
    primary_method: str,
    redirect_path: str | None = None,
) -> ChallengeResult:
    settings = get_settings()
    now = utcnow()
    token = generate_token()
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    await session.execute(
        update(AuthMfaChallenge)
        .where(
            AuthMfaChallenge.user_id == user.id,
            AuthMfaChallenge.purpose == "login",
            AuthMfaChallenge.used_at.is_(None),
            AuthMfaChallenge.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    session.add(
        AuthMfaChallenge(
            user_id=user.id,
            token_hash=hash_token(token),
            purpose="login",
            primary_method=primary_method,
            redirect_path=redirect_path,
            expires_at=now + timedelta(seconds=settings.mfa_challenge_expire_seconds),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    await session.commit()
    return ChallengeResult(token=token, expires_in=settings.mfa_challenge_expire_seconds)


def _audit(session: AsyncSession, user_id: uuid.UUID, action: str, **metadata: object) -> None:
    session.add(
        AdminAuditLog(
            actor_user_id=user_id,
            target_user_id=user_id,
            action=action,
            resource_type="USER",
            resource_id=user_id,
            event_metadata=metadata or None,
        )
    )


def _matching_counter(secret: str, code: str) -> int | None:
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret, digits=6, interval=30, digest=hashlib.sha1)
    current = int(utcnow().timestamp()) // 30
    for offset in range(
        -get_settings().mfa_totp_valid_window, get_settings().mfa_totp_valid_window + 1
    ):
        counter = current + offset
        if hmac.compare_digest(totp.at(counter * 30), code):
            return counter
    return None


async def _consume_factor(
    session: AsyncSession,
    method: UserMfaMethod,
    *,
    code: str | None,
    recovery_code: str | None,
) -> str | None:
    now = utcnow()
    if code:
        counter = _matching_counter(_secret_decrypt(method.secret_encrypted), code.strip())
        if counter is None or (
            method.last_used_counter is not None and counter <= method.last_used_counter
        ):
            return None
        method.last_used_counter = counter
        method.last_used_at = now
        return "totp"
    assert recovery_code is not None
    record = await session.scalar(
        select(UserMfaRecoveryCode)
        .where(
            UserMfaRecoveryCode.user_id == method.user_id,
            UserMfaRecoveryCode.code_hash == recovery_code_hash(recovery_code),
            UserMfaRecoveryCode.used_at.is_(None),
        )
        .with_for_update()
    )
    if not record:
        return None
    record.used_at = now
    method.last_used_at = now
    return "recovery"


async def verify_login_challenge(
    session: AsyncSession,
    token: str,
    *,
    code: str | None,
    recovery_code: str | None,
) -> tuple[User, str, str]:
    settings = get_settings()
    challenge = await session.scalar(
        select(AuthMfaChallenge)
        .where(AuthMfaChallenge.token_hash == hash_token(token))
        .with_for_update()
    )
    now = utcnow()
    if not challenge:
        raise auth_error(
            "MFA_CHALLENGE_INVALID",
            "Die Anmeldung ist ungültig. Bitte melden Sie sich erneut an.",
            status.HTTP_400_BAD_REQUEST,
        )
    if challenge.used_at:
        raise auth_error(
            "MFA_CHALLENGE_USED",
            "Diese Anmeldung wurde bereits abgeschlossen.",
            status.HTTP_409_CONFLICT,
        )
    if challenge.invalidated_at:
        raise auth_error(
            "MFA_CHALLENGE_INVALID",
            "Die Anmeldung ist nicht mehr gültig. Bitte melden Sie sich erneut an.",
            status.HTTP_400_BAD_REQUEST,
        )
    if challenge.expires_at <= now:
        challenge.invalidated_at = now
        await session.commit()
        raise auth_error(
            "MFA_CHALLENGE_EXPIRED",
            "Die Anmeldung ist abgelaufen. Bitte melden Sie sich erneut an.",
            status.HTTP_400_BAD_REQUEST,
        )
    if challenge.attempt_count >= settings.mfa_max_attempts:
        challenge.invalidated_at = now
        await session.commit()
        raise auth_error(
            "MFA_TOO_MANY_ATTEMPTS",
            "Zu viele Fehlversuche. Bitte melden Sie sich erneut an.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    method = await enabled_method(session, challenge.user_id, lock=True)
    user = await session.get(User, challenge.user_id)
    if not method or not user or not user.is_active:
        challenge.invalidated_at = now
        await session.commit()
        raise auth_error(
            "MFA_CHALLENGE_INVALID",
            "Die Anmeldung ist nicht mehr gültig. Bitte melden Sie sich erneut an.",
            status.HTTP_400_BAD_REQUEST,
        )
    used = await _consume_factor(session, method, code=code, recovery_code=recovery_code)
    if not used:
        challenge.attempt_count += 1
        blocked = challenge.attempt_count >= settings.mfa_max_attempts
        if blocked:
            challenge.invalidated_at = now
        _audit(
            session,
            user.id,
            "MFA_CHALLENGE_BLOCKED" if blocked else "MFA_LOGIN_FAILED",
            method="recovery" if recovery_code else "totp",
        )
        await session.commit()
        if blocked:
            raise auth_error(
                "MFA_TOO_MANY_ATTEMPTS",
                "Zu viele Fehlversuche. Bitte melden Sie sich erneut an.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
        code_name = "MFA_RECOVERY_CODE_INVALID" if recovery_code else "MFA_CODE_INVALID"
        raise auth_error(
            code_name, "Der eingegebene Code ist nicht gültig.", status.HTTP_401_UNAUTHORIZED
        )
    challenge.used_at = now
    user.last_login_at = now
    _audit(
        session,
        user.id,
        "MFA_RECOVERY_CODE_USED" if used == "recovery" else "MFA_LOGIN_SUCCESS",
        method=used,
        primary=challenge.primary_method,
    )
    await session.commit()
    await session.refresh(user)
    return user, used, challenge.primary_method


async def start_totp_setup(session: AsyncSession, user: User) -> tuple[str, str]:
    settings = get_settings()
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    if await enabled_method(session, user.id):
        raise auth_error(
            "MFA_ALREADY_ENABLED",
            "Zwei-Faktor-Authentifizierung ist bereits aktiviert.",
            status.HTTP_409_CONFLICT,
        )
    secret = pyotp.random_base32()
    method = await session.scalar(
        select(UserMfaMethod)
        .where(UserMfaMethod.user_id == user.id, UserMfaMethod.type == "totp")
        .with_for_update()
    )
    if method:
        method.secret_encrypted = _secret_encrypt(secret)
        method.setup_expires_at = utcnow() + timedelta(seconds=settings.mfa_setup_expire_seconds)
        method.last_used_counter = None
    else:
        method = UserMfaMethod(
            user_id=user.id,
            type="totp",
            secret_encrypted=_secret_encrypt(secret),
            setup_expires_at=utcnow() + timedelta(seconds=settings.mfa_setup_expire_seconds),
        )
        session.add(method)
    _audit(session, user.id, "MFA_SETUP_STARTED")
    await session.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=settings.mfa_totp_issuer)
    return secret, uri


async def _replace_recovery_codes(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    codes = generate_recovery_codes()
    await session.execute(delete(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == user_id))
    session.add_all(
        UserMfaRecoveryCode(user_id=user_id, code_hash=recovery_code_hash(code)) for code in codes
    )
    return codes


async def confirm_totp_setup(session: AsyncSession, user: User, code: str) -> list[str]:
    method = await session.scalar(
        select(UserMfaMethod)
        .where(UserMfaMethod.user_id == user.id, UserMfaMethod.type == "totp")
        .with_for_update()
    )
    now = utcnow()
    if (
        not method
        or method.is_enabled
        or not method.setup_expires_at
        or method.setup_expires_at <= now
    ):
        raise auth_error(
            "MFA_SETUP_EXPIRED",
            "Die Einrichtung ist abgelaufen. Bitte beginnen Sie erneut.",
            status.HTTP_400_BAD_REQUEST,
        )
    counter = _matching_counter(_secret_decrypt(method.secret_encrypted), code)
    if counter is None:
        raise auth_error(
            "MFA_CODE_INVALID",
            "Der eingegebene Code ist nicht gültig.",
            status.HTTP_401_UNAUTHORIZED,
        )
    method.is_enabled = True
    method.verified_at = now
    method.setup_expires_at = None
    method.last_used_counter = counter
    method.last_used_at = now
    codes = await _replace_recovery_codes(session, user.id)
    _audit(session, user.id, "MFA_ENABLED")
    await session.commit()
    return codes


async def security_status(session: AsyncSession, user_id: uuid.UUID) -> dict[str, object]:
    method = await enabled_method(session, user_id)
    if not method:
        return {
            "enabled": False,
            "method": None,
            "enabled_at": None,
            "last_used_at": None,
            "recovery_codes_remaining": 0,
        }
    remaining = int(
        await session.scalar(
            select(func.count(UserMfaRecoveryCode.id)).where(
                UserMfaRecoveryCode.user_id == user_id, UserMfaRecoveryCode.used_at.is_(None)
            )
        )
        or 0
    )
    return {
        "enabled": True,
        "method": "totp",
        "enabled_at": method.verified_at,
        "last_used_at": method.last_used_at,
        "recovery_codes_remaining": remaining,
    }


async def revoke_other_sessions(
    session: AsyncSession, user_id: uuid.UUID, request: Request, reason: str
) -> None:
    """Revoke other refresh families while preserving this step-up browser."""
    settings = get_settings()
    current_family: uuid.UUID | None = None
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if refresh_token:
        try:
            payload = decode_jwt(refresh_token, "refresh")
            record = await session.scalar(
                select(UserSession).where(UserSession.jti == payload.get("jti"))
            )
            current_family = record.family_id if record and record.user_id == user_id else None
        except jwt.PyJWTError:
            current_family = None
    query = update(UserSession).where(
        UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
    )
    if current_family:
        query = query.where(UserSession.family_id != current_family)
    await session.execute(query.values(revoked_at=utcnow(), revocation_reason=reason))
    await session.commit()


def require_recent_auth(request: Request) -> None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_access_cookie_name)
    try:
        payload = decode_jwt(token or "", "access")
        auth_time = payload.get("auth_time")
    except Exception as exc:
        raise auth_error(
            "MFA_REAUTH_REQUIRED",
            "Bitte melden Sie sich erneut an, um fortzufahren.",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if (
        not isinstance(auth_time, int)
        or int(utcnow().timestamp()) - auth_time > settings.reauth_max_age_seconds
    ):
        raise auth_error(
            "MFA_REAUTH_REQUIRED",
            "Bitte melden Sie sich erneut an, um fortzufahren.",
            status.HTTP_401_UNAUTHORIZED,
        )


async def verify_sensitive_action(
    session: AsyncSession,
    user: User,
    *,
    current_password: str | None,
    code: str | None,
    recovery_code: str | None,
) -> UserMfaMethod:
    method = await enabled_method(session, user.id, lock=True)
    if not method:
        raise auth_error(
            "MFA_NOT_ENABLED",
            "Zwei-Faktor-Authentifizierung ist nicht aktiviert.",
            status.HTTP_409_CONFLICT,
        )
    if user.password_hash and (
        not current_password or not verify_password(current_password, user.password_hash)
    ):
        raise auth_error(
            "INVALID_CREDENTIALS",
            "Das aktuelle Passwort ist nicht korrekt.",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not await _consume_factor(session, method, code=code, recovery_code=recovery_code):
        raise auth_error(
            "MFA_CODE_INVALID",
            "Der eingegebene Code ist nicht gültig.",
            status.HTTP_401_UNAUTHORIZED,
        )
    return method


async def regenerate_recovery_codes(
    session: AsyncSession, user: User, **credentials: str | None
) -> list[str]:
    await verify_sensitive_action(session, user, **credentials)
    codes = await _replace_recovery_codes(session, user.id)
    _audit(session, user.id, "MFA_RECOVERY_CODES_REGENERATED")
    await session.commit()
    return codes


async def disable_mfa(session: AsyncSession, user: User, **credentials: str | None) -> None:
    await verify_sensitive_action(session, user, **credentials)
    now = utcnow()
    await session.execute(delete(UserMfaRecoveryCode).where(UserMfaRecoveryCode.user_id == user.id))
    await session.execute(delete(UserMfaMethod).where(UserMfaMethod.user_id == user.id))
    await session.execute(
        update(AuthMfaChallenge)
        .where(AuthMfaChallenge.user_id == user.id, AuthMfaChallenge.used_at.is_(None))
        .values(invalidated_at=now)
    )
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revocation_reason="mfa_disabled")
    )
    _audit(session, user.id, "MFA_DISABLED")
    await session.commit()

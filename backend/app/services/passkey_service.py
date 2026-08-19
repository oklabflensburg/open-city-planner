import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

from fastapi import Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.auth.tokens import generate_token, hash_token
from app.core.config import get_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.mfa import (
    AuthMfaChallenge,
    UserMfaMethod,
    UserMfaRecoveryCode,
    UserWebAuthnCredential,
    WebAuthnChallenge,
)
from app.models.oauth_account import UserOAuthAccount
from app.models.user import User
from app.services.auth_service import auth_error, inactive_account_error, utcnow

logger = logging.getLogger(__name__)
Purpose = Literal["passkey_register", "passkey_authenticate", "passkey_step_up"]


@dataclass(frozen=True)
class CeremonyOptions:
    token: str
    options: dict[str, Any]


def _audit(session: AsyncSession, user_id: uuid.UUID | None, action: str, **metadata: object) -> None:
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


def _request_metadata(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def _create_ceremony(
    session: AsyncSession,
    request: Request,
    purpose: Purpose,
    challenge: bytes,
    *,
    user_id: uuid.UUID | None = None,
    mfa_challenge_id: uuid.UUID | None = None,
) -> str:
    token = generate_token()
    settings = get_settings()
    session.add(
        WebAuthnChallenge(
            user_id=user_id,
            mfa_challenge_id=mfa_challenge_id,
            token_hash=hash_token(token),
            challenge=challenge,
            purpose=purpose,
            expires_at=utcnow()
            + timedelta(seconds=settings.webauthn_challenge_expire_seconds),
            **_request_metadata(request),
        )
    )
    return token


async def _locked_ceremony(
    session: AsyncSession, token: str, purpose: Purpose
) -> WebAuthnChallenge:
    ceremony = await session.scalar(
        select(WebAuthnChallenge)
        .where(WebAuthnChallenge.token_hash == hash_token(token))
        .with_for_update()
    )
    if not ceremony or ceremony.purpose != purpose or ceremony.invalidated_at:
        raise auth_error(
            "PASSKEY_CHALLENGE_INVALID",
            "Die Passkey-Anfrage ist nicht mehr gültig.",
            status.HTTP_400_BAD_REQUEST,
        )
    if ceremony.used_at:
        raise auth_error(
            "PASSKEY_CHALLENGE_INVALID",
            "Diese Passkey-Anfrage wurde bereits verwendet.",
            status.HTTP_409_CONFLICT,
        )
    if ceremony.expires_at <= utcnow():
        ceremony.invalidated_at = utcnow()
        await session.commit()
        raise auth_error(
            "PASSKEY_CHALLENGE_EXPIRED",
            "Die Passkey-Anfrage ist abgelaufen. Bitte versuchen Sie es erneut.",
            status.HTTP_400_BAD_REQUEST,
        )
    return ceremony


def _descriptor(credential: UserWebAuthnCredential) -> PublicKeyCredentialDescriptor:
    transports = None
    if credential.transports:
        transports = []
        for value in credential.transports:
            try:
                transports.append(AuthenticatorTransport(value))
            except ValueError:
                continue
    return PublicKeyCredentialDescriptor(id=credential.credential_id, transports=transports)


def _credential_id(payload: dict[str, Any]) -> bytes:
    encoded = payload.get("rawId") or payload.get("id")
    if not isinstance(encoded, str):
        raise auth_error(
            "PASSKEY_VERIFICATION_FAILED",
            "Der Passkey konnte nicht geprüft werden.",
            status.HTTP_401_UNAUTHORIZED,
        )
    try:
        return base64url_to_bytes(encoded)
    except Exception as exc:
        raise auth_error(
            "PASSKEY_VERIFICATION_FAILED",
            "Der Passkey konnte nicht geprüft werden.",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc


async def has_passkeys(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(UserWebAuthnCredential.id).where(UserWebAuthnCredential.user_id == user_id)
        )
    )


async def available_mfa_methods(
    session: AsyncSession, user_id: uuid.UUID
) -> list[str]:
    methods: list[str] = []
    if await has_passkeys(session, user_id):
        methods.append("passkey")
    totp = await session.scalar(
        select(UserMfaMethod.id).where(
            UserMfaMethod.user_id == user_id,
            UserMfaMethod.type == "totp",
            UserMfaMethod.is_enabled.is_(True),
        )
    )
    if totp:
        methods.extend(("totp", "recovery_code"))
    return methods


async def registration_options(
    session: AsyncSession, user: User, request: Request
) -> CeremonyOptions:
    settings = get_settings()
    credentials = list(
        (
            await session.scalars(
                select(UserWebAuthnCredential).where(
                    UserWebAuthnCredential.user_id == user.id
                )
            )
        ).all()
    )
    challenge = secrets.token_bytes(32)
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=user.display_name
        or " ".join(value for value in (user.first_name, user.last_name) if value)
        or user.email,
        challenge=challenge,
        timeout=settings.webauthn_timeout_ms,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[_descriptor(value) for value in credentials],
    )
    token = await _create_ceremony(
        session, request, "passkey_register", challenge, user_id=user.id
    )
    _audit(session, user.id, "PASSKEY_REGISTRATION_STARTED")
    await session.commit()
    return CeremonyOptions(token=token, options=json.loads(options_to_json(options)))


async def verify_registration(
    session: AsyncSession,
    user: User,
    ceremony_token: str,
    credential_payload: dict[str, Any],
    name: str | None,
) -> UserWebAuthnCredential:
    ceremony = await _locked_ceremony(session, ceremony_token, "passkey_register")
    if ceremony.user_id != user.id:
        raise auth_error(
            "PASSKEY_CHALLENGE_INVALID",
            "Die Passkey-Anfrage gehört nicht zu diesem Konto.",
            status.HTTP_400_BAD_REQUEST,
        )
    settings = get_settings()
    try:
        verification = verify_registration_response(
            credential=credential_payload,
            expected_challenge=ceremony.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=True,
        )
    except WebAuthnException as exc:
        ceremony.attempt_count += 1
        _audit(session, user.id, "PASSKEY_REGISTRATION_FAILED", reason=type(exc).__name__)
        await session.commit()
        raise auth_error(
            "PASSKEY_VERIFICATION_FAILED",
            "Der Passkey konnte nicht registriert werden.",
            status.HTTP_400_BAD_REQUEST,
        ) from exc
    if await session.scalar(
        select(UserWebAuthnCredential.id).where(
            UserWebAuthnCredential.credential_id == verification.credential_id
        )
    ):
        ceremony.attempt_count += 1
        _audit(session, user.id, "PASSKEY_REGISTRATION_FAILED", reason="duplicate")
        await session.commit()
        raise auth_error(
            "PASSKEY_ALREADY_REGISTERED",
            "Dieser Passkey ist bereits registriert.",
            status.HTTP_409_CONFLICT,
        )
    count = int(
        await session.scalar(
            select(func.count(UserWebAuthnCredential.id)).where(
                UserWebAuthnCredential.user_id == user.id
            )
        )
        or 0
    )
    transports = credential_payload.get("response", {}).get("transports")
    record = UserWebAuthnCredential(
        user_id=user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        name=(name or f"Passkey {count + 1}").strip(),
        aaguid=uuid.UUID(verification.aaguid) if verification.aaguid else None,
        transports=transports if isinstance(transports, list) else None,
        device_type=verification.credential_device_type.value,
        backed_up=verification.credential_backed_up,
    )
    ceremony.used_at = utcnow()
    session.add(record)
    _audit(
        session,
        user.id,
        "PASSKEY_REGISTERED",
        device_type=record.device_type,
        backed_up=record.backed_up,
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        _audit(session, user.id, "PASSKEY_REGISTRATION_FAILED", reason="duplicate_race")
        await session.commit()
        raise auth_error(
            "PASSKEY_ALREADY_REGISTERED",
            "Dieser Passkey ist bereits registriert.",
            status.HTTP_409_CONFLICT,
        ) from exc
    await session.refresh(record)
    return record


async def authentication_options(
    session: AsyncSession,
    request: Request,
    *,
    user_id: uuid.UUID | None = None,
    purpose: Purpose = "passkey_authenticate",
    mfa_challenge_id: uuid.UUID | None = None,
) -> CeremonyOptions:
    settings = get_settings()
    credentials: list[UserWebAuthnCredential] = []
    if user_id:
        credentials = list(
            (
                await session.scalars(
                    select(UserWebAuthnCredential).where(
                        UserWebAuthnCredential.user_id == user_id
                    )
                )
            ).all()
        )
        if not credentials:
            raise auth_error(
                "PASSKEY_NOT_FOUND",
                "Für dieses Konto ist kein Passkey registriert.",
                status.HTTP_404_NOT_FOUND,
            )
    challenge = secrets.token_bytes(32)
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=challenge,
        timeout=settings.webauthn_timeout_ms,
        allow_credentials=[_descriptor(value) for value in credentials] or None,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    token = await _create_ceremony(
        session,
        request,
        purpose,
        challenge,
        user_id=user_id,
        mfa_challenge_id=mfa_challenge_id,
    )
    await session.commit()
    return CeremonyOptions(token=token, options=json.loads(options_to_json(options)))


async def _verify_authentication(
    session: AsyncSession,
    ceremony: WebAuthnChallenge,
    credential_payload: dict[str, Any],
    *,
    expected_user_id: uuid.UUID | None = None,
) -> tuple[User, UserWebAuthnCredential]:
    credential_id = _credential_id(credential_payload)
    record = await session.scalar(
        select(UserWebAuthnCredential)
        .where(UserWebAuthnCredential.credential_id == credential_id)
        .with_for_update()
    )
    if not record or (expected_user_id and record.user_id != expected_user_id):
        ceremony.attempt_count += 1
        _audit(
            session,
            ceremony.user_id,
            "PASSKEY_MFA_FAILED"
            if ceremony.purpose == "passkey_step_up"
            else "PASSKEY_LOGIN_FAILED",
        )
        await session.commit()
        raise auth_error(
            "PASSKEY_VERIFICATION_FAILED",
            "Der Passkey konnte nicht geprüft werden.",
            status.HTTP_401_UNAUTHORIZED,
        )
    user = await session.get(User, record.user_id)
    if not user:
        raise auth_error(
            "PASSKEY_VERIFICATION_FAILED",
            "Der Passkey konnte nicht geprüft werden.",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        raise inactive_account_error(user)
    user_handle = credential_payload.get("response", {}).get("userHandle")
    if user_handle:
        try:
            if base64url_to_bytes(user_handle) != user.id.bytes:
                raise ValueError("user handle mismatch")
        except Exception as exc:
            raise auth_error(
                "PASSKEY_VERIFICATION_FAILED",
                "Der Passkey konnte nicht geprüft werden.",
                status.HTTP_401_UNAUTHORIZED,
            ) from exc
    settings = get_settings()
    try:
        # Verify the signature independently of counter monotonicity. Synced multi-device
        # passkeys can legitimately report zero or regress; regressions are audited below.
        verification = verify_authentication_response(
            credential=credential_payload,
            expected_challenge=ceremony.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=record.public_key,
            credential_current_sign_count=0,
            require_user_verification=True,
        )
    except WebAuthnException as exc:
        ceremony.attempt_count += 1
        _audit(
            session,
            user.id,
            "PASSKEY_MFA_FAILED"
            if ceremony.purpose == "passkey_step_up"
            else "PASSKEY_LOGIN_FAILED",
            reason=type(exc).__name__,
        )
        await session.commit()
        raise auth_error(
            "PASSKEY_VERIFICATION_FAILED",
            "Der Passkey konnte nicht geprüft werden.",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if record.sign_count > 0 and verification.new_sign_count <= record.sign_count:
        _audit(
            session,
            user.id,
            "PASSKEY_COUNTER_REGRESSION",
            previous=record.sign_count,
            received=verification.new_sign_count,
            device_type=verification.credential_device_type.value,
        )
        logger.warning("WebAuthn sign counter regression for user %s", user.id)
    else:
        record.sign_count = verification.new_sign_count
    record.device_type = verification.credential_device_type.value
    record.backed_up = verification.credential_backed_up
    record.last_used_at = utcnow()
    ceremony.used_at = utcnow()
    user.last_login_at = utcnow()
    return user, record


async def verify_passwordless_login(
    session: AsyncSession, ceremony_token: str, credential_payload: dict[str, Any]
) -> User:
    ceremony = await _locked_ceremony(session, ceremony_token, "passkey_authenticate")
    user, _record = await _verify_authentication(session, ceremony, credential_payload)
    _audit(session, user.id, "PASSKEY_LOGIN_SUCCESS")
    await session.commit()
    await session.refresh(user)
    return user


async def verify_reauthentication(
    session: AsyncSession,
    user_id: uuid.UUID,
    ceremony_token: str,
    credential_payload: dict[str, Any],
) -> User:
    ceremony = await _locked_ceremony(session, ceremony_token, "passkey_step_up")
    if ceremony.user_id != user_id or ceremony.mfa_challenge_id is not None:
        raise auth_error(
            "PASSKEY_CHALLENGE_INVALID",
            "Die Passkey-Anfrage gehört nicht zu diesem Konto.",
            status.HTTP_400_BAD_REQUEST,
        )
    user, _record = await _verify_authentication(
        session, ceremony, credential_payload, expected_user_id=user_id
    )
    _audit(session, user.id, "PASSKEY_MFA_SUCCESS", purpose="reauthentication")
    await session.commit()
    await session.refresh(user)
    return user


async def mfa_options(
    session: AsyncSession, request: Request, challenge_token: str
) -> CeremonyOptions:
    challenge = await session.scalar(
        select(AuthMfaChallenge)
        .where(AuthMfaChallenge.token_hash == hash_token(challenge_token))
        .with_for_update()
    )
    if (
        not challenge
        or challenge.used_at
        or challenge.invalidated_at
        or challenge.expires_at <= utcnow()
    ):
        raise auth_error(
            "MFA_CHALLENGE_INVALID",
            "Die Anmeldung ist nicht mehr gültig. Bitte melden Sie sich erneut an.",
            status.HTTP_400_BAD_REQUEST,
        )
    return await authentication_options(
        session,
        request,
        user_id=challenge.user_id,
        purpose="passkey_step_up",
        mfa_challenge_id=challenge.id,
    )


async def verify_mfa(
    session: AsyncSession,
    challenge_token: str,
    ceremony_token: str,
    credential_payload: dict[str, Any],
) -> tuple[User, str]:
    challenge = await session.scalar(
        select(AuthMfaChallenge)
        .where(AuthMfaChallenge.token_hash == hash_token(challenge_token))
        .with_for_update()
    )
    if (
        not challenge
        or challenge.used_at
        or challenge.invalidated_at
        or challenge.expires_at <= utcnow()
    ):
        raise auth_error(
            "MFA_CHALLENGE_INVALID",
            "Die Anmeldung ist nicht mehr gültig. Bitte melden Sie sich erneut an.",
            status.HTTP_400_BAD_REQUEST,
        )
    ceremony = await _locked_ceremony(session, ceremony_token, "passkey_step_up")
    if ceremony.mfa_challenge_id != challenge.id or ceremony.user_id != challenge.user_id:
        raise auth_error(
            "PASSKEY_CHALLENGE_INVALID",
            "Die Passkey-Anfrage gehört nicht zu dieser Anmeldung.",
            status.HTTP_400_BAD_REQUEST,
        )
    user, _record = await _verify_authentication(
        session, ceremony, credential_payload, expected_user_id=challenge.user_id
    )
    challenge.used_at = utcnow()
    _audit(session, user.id, "PASSKEY_MFA_SUCCESS", primary=challenge.primary_method)
    await session.commit()
    await session.refresh(user)
    return user, challenge.primary_method


async def list_passkeys(
    session: AsyncSession, user_id: uuid.UUID
) -> list[UserWebAuthnCredential]:
    return list(
        (
            await session.scalars(
                select(UserWebAuthnCredential)
                .where(UserWebAuthnCredential.user_id == user_id)
                .order_by(UserWebAuthnCredential.created_at.asc())
            )
        ).all()
    )


async def rename_passkey(
    session: AsyncSession, user_id: uuid.UUID, credential_id: uuid.UUID, name: str
) -> UserWebAuthnCredential:
    record = await session.scalar(
        select(UserWebAuthnCredential).where(
            UserWebAuthnCredential.id == credential_id,
            UserWebAuthnCredential.user_id == user_id,
        )
    )
    if not record:
        raise auth_error(
            "PASSKEY_NOT_FOUND", "Passkey nicht gefunden.", status.HTTP_404_NOT_FOUND
        )
    record.name = name
    _audit(session, user_id, "PASSKEY_RENAMED")
    await session.commit()
    await session.refresh(record)
    return record


async def remove_passkey(
    session: AsyncSession, user: User, credential_id: uuid.UUID
) -> bool:
    record = await session.scalar(
        select(UserWebAuthnCredential)
        .where(
            UserWebAuthnCredential.id == credential_id,
            UserWebAuthnCredential.user_id == user.id,
        )
        .with_for_update()
    )
    if not record:
        raise auth_error(
            "PASSKEY_NOT_FOUND", "Passkey nicht gefunden.", status.HTTP_404_NOT_FOUND
        )
    other_passkey = await session.scalar(
        select(UserWebAuthnCredential.id).where(
            UserWebAuthnCredential.user_id == user.id,
            UserWebAuthnCredential.id != record.id,
        )
    )
    totp = await session.scalar(
        select(UserMfaMethod.id).where(
            UserMfaMethod.user_id == user.id,
            UserMfaMethod.is_enabled.is_(True),
        )
    )
    oauth = await session.scalar(
        select(UserOAuthAccount.id).where(UserOAuthAccount.user_id == user.id)
    )
    recovery = await session.scalar(
        select(UserMfaRecoveryCode.id).where(
            UserMfaRecoveryCode.user_id == user.id,
            UserMfaRecoveryCode.used_at.is_(None),
        )
    )
    if not any((user.password_hash, other_passkey, totp, oauth, recovery)):
        raise auth_error(
            "PASSKEY_LAST_METHOD",
            "Dieser Passkey ist Ihre letzte Anmeldemethode und kann nicht entfernt werden.",
            status.HTTP_409_CONFLICT,
        )
    await session.delete(record)
    remaining = bool(other_passkey)
    _audit(session, user.id, "PASSKEY_REMOVED", remaining=remaining)
    await session.commit()
    return remaining

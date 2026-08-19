import hmac
import logging
import urllib.parse
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.auth.csrf import create_csrf_token, validate_csrf, validate_refresh_origin
from app.auth.dependencies import SessionDep, get_current_active_user, get_optional_user
from app.auth.oauth import (
    OAuthFlowState,
    authorization_url,
    configured_providers,
    create_oauth_state,
    decode_oauth_flow,
    encode_oauth_flow,
    exchange_oauth_code,
    oauth_cookie_name,
    provider_is_configured,
    safe_redirect_path,
)
from app.auth.tokens import hash_token
from app.core.config import get_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    MfaChallengeResponse,
    MfaDisableRequest,
    MfaRegenerateRequest,
    MfaSecurityStatus,
    MfaVerifyRequest,
    RecoveryCodesResponse,
    ResetPasswordRequest,
    SignupRequest,
    TokenRequest,
    TotpConfirmRequest,
    TotpSetupResponse,
    VerificationResponse,
)
from app.schemas.oauth import (
    MastodonOAuthLinkRequest,
    MastodonOAuthStartRequest,
    OAuthEmailCompletionRequest,
    OAuthProviderRead,
    OAuthStartRead,
)
from app.schemas.user import UserRead
from app.services.auth_service import (
    authenticate,
    change_password,
    clear_auth_cookies,
    complete_oauth_email,
    forgot_password,
    issue_session,
    refresh_session,
    resend_verification,
    reset_password,
    revoke_all_sessions,
    revoke_current_session,
    signup,
    verify_email,
)
from app.services.email_service import send_mfa_security_email
from app.services.mastodon_sso import (
    consume_mastodon_oauth_flow,
    create_mastodon_oauth_flow,
    exchange_mastodon_oauth_code,
)
from app.services.mfa_service import (
    confirm_totp_setup,
    create_login_challenge,
    disable_mfa,
    regenerate_recovery_codes,
    require_recent_auth,
    revoke_other_sessions,
    security_status,
    start_totp_setup,
    user_requires_mfa,
    verify_login_challenge,
)
from app.services.oauth_account_service import (
    authenticate_oauth_identity,
    get_for_user_provider,
    link_oauth_account,
    normalize_provider,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


@router.get("/providers")
async def get_auth_providers() -> dict[str, list[str]]:
    return {"providers": configured_providers()}


@router.get("/oauth/providers", response_model=list[OAuthProviderRead])
async def get_oauth_providers() -> list[OAuthProviderRead]:
    settings = get_settings()
    return [
        OAuthProviderRead(
            id=provider,
            label=provider_label(provider),
            requires_instance=provider == "mastodon",
            default_instance=(
                settings.mastodon_sso_default_instance if provider == "mastodon" else None
            ),
        )
        for provider in configured_providers()
    ]


@router.post("/oauth/mastodon/start", response_model=OAuthStartRead)
async def start_mastodon_oauth_login(
    payload: MastodonOAuthStartRequest,
    response: Response,
    session: SessionDep,
    request: Request,
) -> OAuthStartRead:
    if not provider_is_configured("mastodon"):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OAUTH_PROVIDER_DISABLED",
                    "message": "Mastodon-Anmeldung ist nicht aktiviert.",
                }
            },
        )
    check_rate_limit(f"mastodon-oauth-start:{request.client.host if request.client else 'unknown'}")
    state, url = await create_mastodon_oauth_flow(
        session,
        payload.instance,
        mode="login",
        redirect_path=safe_redirect_path(payload.redirect),
    )
    set_oauth_flow_cookie(
        response,
        "mastodon",
        OAuthFlowState(state, "login", safe_redirect_path(payload.redirect)),
    )
    return OAuthStartRead(authorization_url=url)


@router.post("/oauth/mastodon/link", response_model=OAuthStartRead)
async def start_mastodon_oauth_link(
    payload: MastodonOAuthLinkRequest,
    response: Response,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> OAuthStartRead:
    validate_csrf(request)
    require_recent_auth(request)
    if not provider_is_configured("mastodon"):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OAUTH_PROVIDER_DISABLED",
                    "message": "Mastodon-Anmeldung ist nicht aktiviert.",
                }
            },
        )
    if await get_for_user_provider(session, user.id, "mastodon"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "OAUTH_ACCOUNT_ALREADY_LINKED",
                    "message": "Ihr Konto ist bereits mit Mastodon verbunden.",
                }
            },
        )
    state, url = await create_mastodon_oauth_flow(
        session,
        payload.instance,
        mode="link",
        redirect_path="/profil",
        user_id=user.id,
    )
    set_oauth_flow_cookie(
        response,
        "mastodon",
        OAuthFlowState(state, "link", "/profil", str(user.id)),
    )
    return OAuthStartRead(authorization_url=url)


@router.post("/oauth/complete-email", response_model=VerificationResponse)
async def post_complete_oauth_email(
    payload: OAuthEmailCompletionRequest,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> VerificationResponse:
    validate_csrf(request)
    await complete_oauth_email(session, user, str(payload.email))
    return VerificationResponse(
        status="verification_sent",
        code="VERIFICATION_EMAIL_SENT",
        message="Bitte bestätigen Sie Ihre E-Mail-Adresse über den zugesandten Link.",
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def post_signup(
    payload: SignupRequest, session: SessionDep, response: Response, request: Request
) -> AuthResponse:
    check_rate_limit(
        f"signup:{request.client.host if request.client else 'unknown'}:{payload.email}"
    )
    user = await signup(session, payload)
    csrf_token = await issue_session(session, response, user, request)
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"description": "Ungültige E-Mail-Adresse oder ungültiges Passwort"},
        403: {
            "description": (
                "Das Konto kann nicht angemeldet werden. Mögliche Fehlercodes sind "
                "ACCOUNT_SELF_DEACTIVATED und ACCOUNT_DISABLED."
            )
        },
    },
)
async def post_login(
    payload: LoginRequest, session: SessionDep, response: Response, request: Request
) -> LoginResponse:
    check_rate_limit(
        f"login:{request.client.host if request.client else 'unknown'}:{payload.email}"
    )
    user = await authenticate(session, payload)
    if await user_requires_mfa(session, user.id):
        challenge = await create_login_challenge(session, user, request, primary_method="password")
        return MfaChallengeResponse(
            challenge_token=challenge.token, expires_in=challenge.expires_in
        )
    csrf_token = await issue_session(session, response, user, request, amr=["pwd"])
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.post("/mfa/verify", response_model=AuthResponse)
async def post_mfa_verify(
    payload: MfaVerifyRequest, session: SessionDep, response: Response, request: Request
) -> AuthResponse:
    settings = get_settings()
    fingerprint = hash_token(payload.challenge_token)[:24]
    check_rate_limit(
        f"mfa-verify:{request.client.host if request.client else 'unknown'}:{fingerprint}",
        attempts=settings.mfa_max_attempts,
        window_seconds=settings.mfa_challenge_expire_seconds,
        code="MFA_TOO_MANY_ATTEMPTS",
        message="Zu viele Fehlversuche. Bitte melden Sie sich erneut an.",
    )
    user, factor, primary_method = await verify_login_challenge(
        session,
        payload.challenge_token,
        code=payload.code,
        recovery_code=payload.recovery_code,
    )
    primary = "oauth" if primary_method.startswith("oauth") else "pwd"
    csrf_token = await issue_session(
        session, response, user, request, amr=[primary, "otp" if factor == "totp" else "recovery"]
    )
    if factor == "recovery":
        send_mfa_security_email(user, "recovery_used")
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.get("/mfa/security", response_model=MfaSecurityStatus)
async def get_mfa_security(
    session: SessionDep, user: Annotated[User, Depends(get_current_active_user)]
) -> MfaSecurityStatus:
    return MfaSecurityStatus(**await security_status(session, user.id))


@router.post("/mfa/totp/setup", response_model=TotpSetupResponse)
async def post_totp_setup(
    session: SessionDep, request: Request, user: Annotated[User, Depends(get_current_active_user)]
) -> TotpSetupResponse:
    validate_csrf(request)
    require_recent_auth(request)
    settings = get_settings()
    check_rate_limit(f"mfa-setup:{user.id}", attempts=3, window_seconds=600)
    secret, uri = await start_totp_setup(session, user)
    return TotpSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        issuer=settings.mfa_totp_issuer,
        account_name=user.email,
        expires_in=settings.mfa_setup_expire_seconds,
    )


@router.post("/mfa/totp/confirm", response_model=RecoveryCodesResponse)
async def post_totp_confirm(
    payload: TotpConfirmRequest,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> RecoveryCodesResponse:
    validate_csrf(request)
    check_rate_limit(f"mfa-confirm:{user.id}", attempts=5, window_seconds=600)
    codes = await confirm_totp_setup(session, user, payload.code)
    await revoke_other_sessions(session, user.id, request, "mfa_enabled")
    send_mfa_security_email(user, "enabled")
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesResponse)
async def post_recovery_codes(
    payload: MfaRegenerateRequest,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> RecoveryCodesResponse:
    validate_csrf(request)
    check_rate_limit(f"mfa-recovery-regenerate:{user.id}", attempts=3, window_seconds=600)
    codes = await regenerate_recovery_codes(
        session,
        user,
        current_password=payload.current_password,
        code=payload.code,
        recovery_code=payload.recovery_code,
    )
    await revoke_other_sessions(session, user.id, request, "mfa_recovery_regenerated")
    send_mfa_security_email(user, "recovery_regenerated")
    return RecoveryCodesResponse(recovery_codes=codes)


@router.delete("/mfa/totp", response_model=MessageResponse)
async def delete_totp(
    payload: MfaDisableRequest,
    session: SessionDep,
    response: Response,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> MessageResponse:
    validate_csrf(request)
    check_rate_limit(f"mfa-disable:{user.id}", attempts=3, window_seconds=600)
    await disable_mfa(
        session,
        user,
        current_password=payload.current_password,
        code=payload.code,
        recovery_code=payload.recovery_code,
    )
    clear_auth_cookies(response)
    send_mfa_security_email(user, "disabled")
    return MessageResponse(
        message="Zwei-Faktor-Authentifizierung wurde deaktiviert. Bitte melden Sie sich erneut an."
    )


@router.post("/refresh", response_model=AuthResponse)
async def post_refresh(session: SessionDep, response: Response, request: Request) -> AuthResponse:
    settings = get_settings()
    validate_refresh_origin(request)
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if not refresh_token:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "REFRESH_TOKEN_MISSING",
                    "message": "Bitte melden Sie sich erneut an.",
                }
            },
        )
    check_rate_limit(
        f"refresh:{request.client.host if request.client else 'unknown'}:{hash_token(refresh_token)[:16]}",
        attempts=settings.refresh_rate_limit_attempts,
        window_seconds=settings.refresh_rate_limit_window_seconds,
        code="REFRESH_RATE_LIMITED",
        message="Zu viele Sitzungsaktualisierungen. Bitte kurz warten.",
    )
    try:
        user, csrf_token = await refresh_session(session, response, refresh_token, request)
    except HTTPException as exc:
        error_code = (
            exc.detail.get("error", {}).get("code") if isinstance(exc.detail, dict) else None
        )
        if exc.status_code == status.HTTP_401_UNAUTHORIZED or error_code in {
            "ACCOUNT_SELF_DEACTIVATED",
            "ACCOUNT_DISABLED",
        }:
            clear_auth_cookies(response)
        raise
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", response_model=MessageResponse)
async def post_logout(session: SessionDep, response: Response, request: Request) -> MessageResponse:
    validate_csrf(request)
    settings = get_settings()
    await revoke_current_session(session, request.cookies.get(settings.auth_refresh_cookie_name))
    clear_auth_cookies(response)
    return MessageResponse(message="Abgemeldet.")


@router.post("/logout-all", response_model=MessageResponse)
async def post_logout_all(
    session: SessionDep,
    response: Response,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> MessageResponse:
    validate_csrf(request)
    await revoke_all_sessions(session, user.id)
    clear_auth_cookies(response)
    return MessageResponse(message="Alle Sitzungen wurden beendet.")


@router.get("/me", response_model=UserRead)
async def get_me(user: Annotated[User, Depends(get_current_active_user)]) -> UserRead:
    return UserRead.model_validate(user)


@router.get("/session", response_model=AuthResponse)
async def get_auth_session(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_active_user)],
) -> AuthResponse:
    settings = get_settings()
    csrf_token = request.cookies.get(settings.auth_csrf_cookie_name) or create_csrf_token()
    if not request.cookies.get(settings.auth_csrf_cookie_name):
        response.set_cookie(
            settings.auth_csrf_cookie_name,
            csrf_token,
            httponly=False,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
            domain=settings.auth_cookie_domain,
            path=settings.auth_cookie_path,
            max_age=settings.refresh_token_expire_days * 86400,
        )
    return AuthResponse(user=UserRead.model_validate(user), csrf_token=csrf_token)


@router.post("/verify-email", response_model=VerificationResponse)
async def post_verify_email(payload: TokenRequest, session: SessionDep) -> VerificationResponse:
    result = await verify_email(session, payload.token)
    if result.status == "already_verified":
        return VerificationResponse(
            status="already_verified",
            code="EMAIL_ALREADY_VERIFIED",
            message="Die E-Mail-Adresse wurde bereits bestätigt.",
        )
    return VerificationResponse(
        status="verified",
        code="EMAIL_VERIFIED",
        message="E-Mail-Adresse bestätigt.",
    )


@router.post("/resend-verification", response_model=VerificationResponse)
async def post_resend_verification(
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> VerificationResponse:
    validate_csrf(request)
    check_rate_limit(f"resend-verification:{user.id}")
    sent = await resend_verification(session, user)
    if not sent:
        return VerificationResponse(
            status="already_verified",
            code="EMAIL_ALREADY_VERIFIED",
            message="Die E-Mail-Adresse wurde bereits bestätigt.",
        )
    return VerificationResponse(
        status="verification_sent",
        code="VERIFICATION_EMAIL_SENT",
        message="Bestätigungs-E-Mail wurde gesendet.",
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def post_forgot_password(
    payload: ForgotPasswordRequest, session: SessionDep, request: Request
) -> MessageResponse:
    check_rate_limit(
        f"forgot-password:{request.client.host if request.client else 'unknown'}:{payload.email}"
    )
    await forgot_password(session, str(payload.email), request)
    return MessageResponse(
        message="Wenn ein Konto mit dieser E-Mail-Adresse existiert, wurde eine E-Mail zum Zurücksetzen des Passworts versendet."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def post_reset_password(
    payload: ResetPasswordRequest, session: SessionDep
) -> MessageResponse:
    check_rate_limit(f"reset-password:{payload.token[:16]}")
    await reset_password(session, payload.token, payload.password)
    return MessageResponse(message="Passwort wurde zurückgesetzt.")


@router.post("/change-password", response_model=MessageResponse)
async def post_change_password(
    payload: ChangePasswordRequest,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> MessageResponse:
    validate_csrf(request)
    await change_password(session, user, payload.current_password, payload.new_password)
    return MessageResponse(message="Passwort wurde geändert.")


@router.get("/oauth/{provider}/login")
async def oauth_login(provider: str, redirect: str | None = None) -> RedirectResponse:
    provider = normalize_provider(provider)
    if not provider_is_configured(provider):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OAUTH_PROVIDER_DISABLED",
                    "message": "Dieser OAuth-Provider ist nicht konfiguriert.",
                }
            },
        )
    state = create_oauth_state()
    response = RedirectResponse(authorization_url(provider, state), status_code=302)
    settings = get_settings()
    response.set_cookie(
        oauth_cookie_name(provider),
        encode_oauth_flow(
            OAuthFlowState(
                state=state,
                mode="login",
                redirect_path=safe_redirect_path(redirect),
            )
        ),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=600,
        path="/api/v1/auth/oauth",
        domain=settings.auth_cookie_domain,
    )
    return response


@router.get("/oauth/{provider}/link")
async def oauth_link(
    provider: str,
    session: SessionDep,
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
) -> RedirectResponse:
    require_recent_auth(request)
    provider = normalize_provider(provider)
    if not provider_is_configured(provider):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OAUTH_PROVIDER_DISABLED",
                    "message": "Dieser OAuth-Provider ist nicht konfiguriert.",
                }
            },
        )
    settings = get_settings()
    if await get_for_user_provider(session, user.id, provider):
        response = oauth_link_result_redirect(provider, success="already_connected")
        clear_oauth_cookie(response, provider)
        return response
    state = create_oauth_state()
    response = RedirectResponse(authorization_url(provider, state), status_code=302)
    response.set_cookie(
        oauth_cookie_name(provider),
        encode_oauth_flow(
            OAuthFlowState(
                state=state,
                mode="link",
                redirect_path="/profil",
                user_id=str(user.id),
            )
        ),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=600,
        path="/api/v1/auth/oauth",
        domain=settings.auth_cookie_domain,
    )
    return response


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    state: str,
    session: SessionDep,
    request: Request,
    response: Response,
    code: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    provider = normalize_provider(provider)
    settings = get_settings()
    if not provider_is_configured(provider):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "OAUTH_PROVIDER_DISABLED",
                    "message": "Dieser OAuth-Provider ist nicht konfiguriert.",
                }
            },
        )
    flow = decode_oauth_flow(request.cookies.get(oauth_cookie_name(provider)))
    if not flow:
        redirect_response = oauth_login_error_redirect("INVALID_OAUTH_STATE")
        clear_oauth_cookie(redirect_response, provider)
        return redirect_response
    if not hmac.compare_digest(flow.state, state):
        return oauth_flow_error_redirect(flow.mode, provider, "INVALID_OAUTH_STATE")
    mastodon_grant = None
    if provider == "mastodon":
        mastodon_grant = await consume_mastodon_oauth_flow(session, state)
        if (
            not mastodon_grant
            or mastodon_grant.mode != flow.mode
            or str(mastodon_grant.user_id or "") != (flow.user_id or "")
            or mastodon_grant.redirect_path != flow.redirect_path
        ):
            await audit_oauth_failure(session, provider, None, "INVALID_OAUTH_STATE", flow.user_id)
            return oauth_flow_error_redirect(flow.mode, provider, "INVALID_OAUTH_STATE")
    if error or not code:
        if provider == "mastodon":
            await audit_oauth_failure(
                session,
                provider,
                mastodon_grant.instance_origin if mastodon_grant else None,
                "OAUTH_ACCESS_DENIED",
                flow.user_id,
            )
        return oauth_flow_error_redirect(flow.mode, provider, "OAUTH_ACCESS_DENIED")
    try:
        identity = (
            await exchange_mastodon_oauth_code(session, mastodon_grant, code)
            if provider == "mastodon" and mastodon_grant
            else await exchange_oauth_code(provider, code)
        )
    except HTTPException:
        if provider == "mastodon":
            await audit_oauth_failure(
                session,
                provider,
                mastodon_grant.instance_origin if mastodon_grant else None,
                flow_error_code(flow.mode),
                flow.user_id,
            )
        return oauth_flow_error_redirect(flow.mode, provider, flow_error_code(flow.mode))
    except Exception:
        logger.exception(
            "OAuth code exchange failed provider=%s instance=%s",
            provider,
            mastodon_grant.instance_origin if mastodon_grant else None,
        )
        if provider == "mastodon":
            await audit_oauth_failure(
                session,
                provider,
                mastodon_grant.instance_origin if mastodon_grant else None,
                flow_error_code(flow.mode),
                flow.user_id,
            )
        return oauth_flow_error_redirect(flow.mode, provider, flow_error_code(flow.mode))
    if flow.mode == "link":
        current_user = await get_optional_user(request, session)
        if not current_user or str(current_user.id) != flow.user_id:
            return oauth_flow_error_redirect("link", provider, "AUTH_REQUIRED")
        try:
            await link_oauth_account(session, current_user, identity)
        except HTTPException as exc:
            code_value = (
                exc.detail.get("error", {}).get("code", "OAUTH_LINK_FAILED")
                if isinstance(exc.detail, dict)
                else "OAUTH_LINK_FAILED"
            )
            if provider == "mastodon":
                await audit_oauth_failure(
                    session,
                    provider,
                    identity.provider_instance,
                    code_value,
                    flow.user_id,
                    link=True,
                )
            redirect_response = oauth_link_result_redirect(provider, error=code_value)
            clear_oauth_cookie(redirect_response, provider)
            return redirect_response
        redirect_response = oauth_link_result_redirect(provider, success="success")
        clear_oauth_cookie(redirect_response, provider)
        return redirect_response

    try:
        user = await authenticate_oauth_identity(session, identity)
    except HTTPException as exc:
        code_value = (
            exc.detail.get("error", {}).get("code", "OAUTH_LOGIN_FAILED")
            if isinstance(exc.detail, dict)
            else "OAUTH_LOGIN_FAILED"
        )
        return oauth_flow_error_redirect("login", provider, code_value)
    callback_url = f"{settings.app_base_url.rstrip('/')}/auth/callback"
    redirect_path = (
        "/profil?oauth_onboarding=email"
        if user.email_pending
        else safe_redirect_path(flow.redirect_path)
    )
    if await user_requires_mfa(session, user.id):
        challenge = await create_login_challenge(
            session,
            user,
            request,
            primary_method=f"oauth:{provider}",
            redirect_path=redirect_path,
        )
        mfa_query = urllib.parse.urlencode(
            {"challenge": challenge.token, "redirect": redirect_path}
        )
        redirect_response = RedirectResponse(
            f"{settings.app_base_url.rstrip('/')}/auth/mfa?{mfa_query}",
            status_code=302,
        )
        clear_oauth_cookie(redirect_response, provider)
        return redirect_response
    callback_query = urllib.parse.urlencode({"redirect": redirect_path})
    redirect_response = RedirectResponse(f"{callback_url}?{callback_query}", status_code=302)
    await issue_session(session, redirect_response, user, request, amr=["oauth"])
    redirect_response.delete_cookie(
        oauth_cookie_name(provider), path="/api/v1/auth/oauth", domain=settings.auth_cookie_domain
    )
    return redirect_response


def provider_label(provider: str) -> str:
    return {
        "github": "GitHub",
        "google": "Google",
        "mastodon": "Mastodon",
    }.get(provider, provider.capitalize())


def oauth_login_error_redirect(code: str) -> RedirectResponse:
    settings = get_settings()
    return RedirectResponse(
        f"{settings.app_base_url.rstrip('/')}/login?auth_error={code}", status_code=302
    )


def oauth_link_result_redirect(
    provider: str,
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    query = {"provider": normalize_provider(provider)}
    if success:
        query["oauth_link"] = success
    if error:
        query["oauth_link_error"] = error
    return RedirectResponse(
        f"{settings.app_base_url.rstrip('/')}/profil?{urllib.parse.urlencode(query)}",
        status_code=302,
    )


def oauth_flow_error_redirect(mode: str, provider: str, code: str) -> RedirectResponse:
    if mode == "link":
        response = oauth_link_result_redirect(provider, error=code)
    else:
        response = oauth_login_error_redirect(code)
    clear_oauth_cookie(response, provider)
    return response


def flow_error_code(mode: str) -> str:
    return "OAUTH_LINK_FAILED" if mode == "link" else "OAUTH_LOGIN_FAILED"


def clear_oauth_cookie(response: RedirectResponse, provider: str) -> None:
    settings = get_settings()
    response.delete_cookie(
        oauth_cookie_name(provider),
        path="/api/v1/auth/oauth",
        domain=settings.auth_cookie_domain,
    )


def set_oauth_flow_cookie(
    response: Response,
    provider: str,
    flow: OAuthFlowState,
) -> None:
    settings = get_settings()
    response.set_cookie(
        oauth_cookie_name(provider),
        encode_oauth_flow(flow),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.mastodon_sso_state_ttl_seconds,
        path="/api/v1/auth/oauth",
        domain=settings.auth_cookie_domain,
    )


async def audit_oauth_failure(
    session: SessionDep,
    provider: str,
    provider_instance: str | None,
    error_code: str,
    user_id: str | None,
    *,
    link: bool = False,
) -> None:
    try:
        actor_id = uuid.UUID(user_id) if user_id else None
    except ValueError:
        actor_id = None
    session.add(
        AdminAuditLog(
            actor_user_id=actor_id,
            target_user_id=actor_id,
            action="OAUTH_ACCOUNT_LINK_FAILED" if link else "OAUTH_LOGIN_FAILED",
            resource_type="USER" if actor_id else None,
            resource_id=actor_id,
            event_metadata={
                "provider": provider,
                "provider_instance": provider_instance,
                "error_code": error_code,
            },
        )
    )
    await session.commit()

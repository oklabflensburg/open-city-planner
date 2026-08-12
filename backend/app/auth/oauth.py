import base64
import hashlib
import hmac
import json
import secrets
import urllib.parse
from dataclasses import dataclass

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import HTTPException, status

from app.auth.tokens import generate_token
from app.core.config import get_settings
from app.schemas.oauth import OAuthIdentity
from app.services.oauth_account_service import normalize_provider


@dataclass(frozen=True)
class OAuthFlowState:
    state: str
    mode: str
    redirect_path: str
    user_id: str | None = None


def configured_providers() -> list[str]:
    return get_settings().configured_oauth_providers


def provider_is_configured(provider: str) -> bool:
    return normalize_provider(provider) in configured_providers()


def safe_redirect_path(path: str | None) -> str:
    if not path:
        return "/"
    candidate = path.strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
    ):
        return "/"
    return candidate


def create_oauth_state() -> str:
    return generate_token()


def encode_oauth_flow(flow: OAuthFlowState) -> str:
    payload = json.dumps(
        {
            "state": flow.state,
            "mode": flow.mode,
            "redirect_path": safe_redirect_path(flow.redirect_path),
            "user_id": flow.user_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(
        get_settings().jwt_secret_key.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"


def decode_oauth_flow(value: str | None) -> OAuthFlowState | None:
    if not value:
        return None
    try:
        encoded, signature = value.rsplit(".", 1)
        expected = hmac.new(
            get_settings().jwt_secret_key.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        state = payload.get("state")
        mode = payload.get("mode")
        redirect_path = payload.get("redirect_path")
        user_id = payload.get("user_id")
        if not isinstance(state, str) or mode not in {"login", "link"}:
            return None
        if not isinstance(redirect_path, str):
            return None
        if user_id is not None and not isinstance(user_id, str):
            return None
        if mode == "link" and not user_id:
            return None
        return OAuthFlowState(
            state=state,
            mode=mode,
            redirect_path=safe_redirect_path(redirect_path),
            user_id=user_id,
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def oauth_cookie_name(provider: str) -> str:
    return f"ocm_oauth_state_{normalize_provider(provider)}"


def oauth_redirect_uri(provider: str) -> str:
    settings = get_settings()
    base = settings.oauth_redirect_base_url or settings.api_base_url
    return f"{base.rstrip('/')}/api/v1/auth/oauth/{normalize_provider(provider)}/callback"


def authorization_url(provider: str, state: str) -> str:
    provider = normalize_provider(provider)
    settings = get_settings()
    redirect_uri = oauth_redirect_uri(provider)
    if provider == "github":
        query = urllib.parse.urlencode({
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        })
        return f"https://github.com/login/oauth/authorize?{query}"
    if provider == "google":
        query = urllib.parse.urlencode({
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": secrets.token_urlsafe(24),
        })
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    raise HTTPException(status_code=404, detail={"error": {"code": "OAUTH_PROVIDER_DISABLED", "message": "Dieser OAuth-Provider ist nicht konfiguriert."}})


async def exchange_oauth_code(provider: str, code: str) -> OAuthIdentity:
    provider = normalize_provider(provider)
    if provider == "github":
        return await exchange_github(code)
    if provider == "google":
        return await exchange_google(code)
    raise HTTPException(status_code=404, detail={"error": {"code": "OAUTH_PROVIDER_DISABLED", "message": "Dieser OAuth-Provider ist nicht konfiguriert."}})


async def exchange_github(code: str) -> OAuthIdentity:
    settings = get_settings()
    oauth_client = AsyncOAuth2Client(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        redirect_uri=oauth_redirect_uri("github"),
        timeout=15,
    )
    token = await oauth_client.fetch_token(
            "https://github.com/login/oauth/access_token",
            code=code,
            headers={"Accept": "application/json"},
        )
    access_token = token.get("access_token")
    if not access_token:
        raise oauth_error()
    async with httpx.AsyncClient(timeout=15) as client:
        user_response = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        user_response.raise_for_status()
        profile = user_response.json()
        emails_response = await client.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        emails = emails_response.json() if emails_response.status_code == 200 else []
    verified_email = next((item.get("email") for item in emails if item.get("primary") and item.get("verified")), None)
    return OAuthIdentity(
        provider="github",
        subject=str(profile["id"]),
        email=verified_email,
        email_verified=bool(verified_email),
        username=profile.get("login"),
        display_name=profile.get("name") or profile.get("login"),
        avatar_url=profile.get("avatar_url"),
    )


async def exchange_google(code: str) -> OAuthIdentity:
    settings = get_settings()
    oauth_client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=oauth_redirect_uri("google"),
        timeout=15,
    )
    token = await oauth_client.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code,
        )
    access_token = token.get("access_token")
    if not access_token:
        raise oauth_error()
    async with httpx.AsyncClient(timeout=15) as client:
        user_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        user_response.raise_for_status()
        profile = user_response.json()
    return OAuthIdentity(
        provider="google",
        subject=str(profile["sub"]),
        email=profile.get("email") if profile.get("email_verified") else None,
        email_verified=bool(profile.get("email_verified")),
        username=profile.get("email"),
        display_name=profile.get("name"),
        avatar_url=profile.get("picture"),
    )


def oauth_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": {"code": "INVALID_OAUTH_CALLBACK", "message": "OAuth-Anmeldung fehlgeschlagen."}})

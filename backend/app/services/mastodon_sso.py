import asyncio
import base64
import hashlib
import ipaddress
import socket
import urllib.parse
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oauth import oauth_redirect_uri, safe_redirect_path
from app.auth.tokens import generate_token, hash_token
from app.core.config import Settings, get_settings
from app.models.oauth_account import MastodonOAuthInstance, OAuthFlowGrant
from app.observability.external import instrumented_httpx_request
from app.schemas.oauth import OAuthIdentity

Resolver = Callable[[str, int], Awaitable[set[ipaddress.IPv4Address | ipaddress.IPv6Address]]]


@dataclass(frozen=True)
class MastodonAppCredentials:
    instance_origin: str
    client_id: str
    client_secret: str
    scope: str


@dataclass(frozen=True)
class MastodonInstanceInfo:
    origin: str
    scope: str
    version: str


def utcnow() -> datetime:
    return datetime.now(UTC)


def mastodon_sso_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def normalize_mastodon_instance(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("@"):
        candidate = candidate.rsplit("@", 1)[-1]
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        parsed = urllib.parse.urlsplit(candidate)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
    except (UnicodeError, ValueError) as exc:
        raise mastodon_sso_error(
            "MASTODON_INSTANCE_INVALID",
            "Bitte geben Sie eine gültige Mastodon-Instanz an.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or len(host) > 253
        or "_" in host
        or "." not in host
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal"))
    ):
        raise mastodon_sso_error(
            "MASTODON_INSTANCE_INVALID",
            "Bitte geben Sie eine öffentliche Mastodon-Instanz mit HTTPS an.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise mastodon_sso_error(
            "MASTODON_INSTANCE_PRIVATE",
            "Private oder lokale Netzwerkadressen sind nicht erlaubt.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise mastodon_sso_error(
            "MASTODON_INSTANCE_INVALID",
            "Der angegebene Port ist ungültig.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ) from exc
    authority = f"[{host}]" if ":" in host else host
    if port and port != 443:
        authority = f"{authority}:{port}"
    return f"https://{authority}"


async def resolve_public_host(
    host: str,
    port: int,
) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise mastodon_sso_error(
            "MASTODON_INSTANCE_UNREACHABLE",
            "Die Mastodon-Instanz ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
    addresses = {ipaddress.ip_address(record[4][0]) for record in records}
    if not addresses or any(not address.is_global for address in addresses):
        raise mastodon_sso_error(
            "MASTODON_INSTANCE_PRIVATE",
            "Private oder lokale Netzwerkadressen sind nicht erlaubt.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return addresses


class MastodonSSOClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = resolve_public_host,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport
        self.resolver = resolver

    async def validate_instance(self, origin: str) -> MastodonInstanceInfo:
        discovery = await self._request(
            "GET",
            f"{origin}/.well-known/oauth-authorization-server",
            allow_not_found=True,
        )
        scope = "read:accounts"
        if discovery.status_code == 200:
            payload = self._json_object(discovery)
            supported = payload.get("scopes_supported")
            if isinstance(supported, list) and "profile" in supported:
                scope = "profile"
            self._require_same_origin_endpoint(payload.get("authorization_endpoint"), origin)
            self._require_same_origin_endpoint(payload.get("token_endpoint"), origin)

        instance_response = await self._request(
            "GET",
            f"{origin}/api/v2/instance",
            allow_not_found=True,
        )
        if instance_response.status_code == 404:
            instance_response = await self._request("GET", f"{origin}/api/v1/instance")
        payload = self._json_object(instance_response)
        version = payload.get("version")
        domain = payload.get("domain")
        if not isinstance(version, str) or not version or not isinstance(domain, str) or not domain:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNSUPPORTED",
                "Diese Adresse scheint keine unterstützte Mastodon-Instanz zu sein.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        return MastodonInstanceInfo(origin=origin, scope=scope, version=version[:120])

    async def register_application(
        self,
        info: MastodonInstanceInfo,
    ) -> tuple[str, str]:
        response = await self._request(
            "POST",
            f"{info.origin}/api/v1/apps",
            data={
                "client_name": self.settings.mastodon_sso_client_name,
                "redirect_uris": oauth_redirect_uri("mastodon"),
                "scopes": info.scope,
                "website": self.settings.app_base_url.rstrip("/"),
            },
        )
        payload = self._json_object(response)
        client_id = payload.get("client_id")
        client_secret = payload.get("client_secret")
        if not isinstance(client_id, str) or not client_id or not isinstance(client_secret, str) or not client_secret:
            raise mastodon_sso_error(
                "MASTODON_APP_REGISTRATION_FAILED",
                "Die Mastodon-Instanz konnte die Anmeldung derzeit nicht vorbereiten.",
                status.HTTP_502_BAD_GATEWAY,
            )
        return client_id, client_secret

    async def exchange_code(
        self,
        credentials: MastodonAppCredentials,
        code: str,
        code_verifier: str,
    ) -> OAuthIdentity:
        token_response = await self._request(
            "POST",
            f"{credentials.instance_origin}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "redirect_uri": oauth_redirect_uri("mastodon"),
                "code_verifier": code_verifier,
            },
        )
        access_token = self._json_object(token_response).get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise mastodon_sso_error(
                "INVALID_OAUTH_CALLBACK",
                "Die Mastodon-Anmeldung konnte nicht abgeschlossen werden.",
                status.HTTP_401_UNAUTHORIZED,
            )
        account_response = await self._request(
            "GET",
            f"{credentials.instance_origin}/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile = self._json_object(account_response)
        subject = profile.get("id")
        username = profile.get("username")
        if not isinstance(subject, (str, int)) or not isinstance(username, str) or not username:
            raise mastodon_sso_error(
                "INVALID_OAUTH_IDENTITY",
                "Die Mastodon-Identität konnte nicht gelesen werden.",
                status.HTTP_401_UNAUTHORIZED,
            )
        host = urllib.parse.urlsplit(credentials.instance_origin).hostname or ""
        acct = profile.get("acct") if isinstance(profile.get("acct"), str) else username
        handle = f"@{acct}" if "@" in acct else f"@{acct}@{host}"
        profile_url = profile.get("url")
        if not isinstance(profile_url, str) or not profile_url.startswith(
            f"{credentials.instance_origin}/"
        ):
            profile_url = None
        return OAuthIdentity(
            provider="mastodon",
            provider_instance=credentials.instance_origin,
            subject=str(subject),
            email=None,
            email_verified=False,
            username=handle,
            display_name=(profile.get("display_name") or username)[:180],
            avatar_url=profile.get("avatar_static") or profile.get("avatar"),
            profile_url=profile_url,
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        allow_not_found: bool = False,
        _redirect_count: int = 0,
        **kwargs: object,
    ) -> httpx.Response:
        parsed = urllib.parse.urlsplit(url)
        origin = normalize_mastodon_instance(
            urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        )
        await self.resolver(parsed.hostname or "", parsed.port or 443)
        timeout = httpx.Timeout(self.settings.mastodon_sso_timeout_seconds)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await instrumented_httpx_request(
                    client,
                    method,
                    url,
                    provider="mastodon_sso",
                    operation=parsed.path,
                    **kwargs,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNREACHABLE",
                "Die Mastodon-Instanz ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        self._validate_peer_address(response)
        if response.is_redirect:
            if _redirect_count >= 2:
                raise mastodon_sso_error(
                    "MASTODON_INSTANCE_REDIRECT_BLOCKED",
                    "Die Mastodon-Instanz hat zu oft weitergeleitet.",
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                )
            location = response.headers.get("location", "")
            redirected = urllib.parse.urljoin(url, location)
            redirected_parts = urllib.parse.urlsplit(redirected)
            redirected_origin = normalize_mastodon_instance(
                urllib.parse.urlunsplit(
                    (redirected_parts.scheme, redirected_parts.netloc, "", "", "")
                )
            )
            await self.resolver(redirected_parts.hostname or "", redirected_parts.port or 443)
            if redirected_origin != origin:
                raise mastodon_sso_error(
                    "MASTODON_INSTANCE_REDIRECT_BLOCKED",
                    "Die Mastodon-Instanz hat auf eine nicht erlaubte Adresse weitergeleitet.",
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                )
            return await self._request(
                method,
                redirected,
                allow_not_found=allow_not_found,
                _redirect_count=_redirect_count + 1,
                **kwargs,
            )
        if allow_not_found and response.status_code == 404:
            return response
        if response.status_code == 429:
            raise mastodon_sso_error(
                "MASTODON_RATE_LIMITED",
                "Die Mastodon-Instanz ist ausgelastet. Bitte versuchen Sie es später erneut.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if response.status_code >= 500:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNREACHABLE",
                "Die Mastodon-Instanz ist derzeit nicht erreichbar. Bitte versuchen Sie es später erneut.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not response.is_success:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNSUPPORTED",
                "Diese Instanz unterstützt derzeit nicht die benötigte Mastodon-OAuth-Schnittstelle.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        return response

    @staticmethod
    def _json_object(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNSUPPORTED",
                "Diese Adresse scheint keine unterstützte Mastodon-Instanz zu sein.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            ) from exc
        if not isinstance(payload, dict):
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNSUPPORTED",
                "Diese Adresse scheint keine unterstützte Mastodon-Instanz zu sein.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        return payload

    @staticmethod
    def _require_same_origin_endpoint(value: object, origin: str) -> None:
        if not isinstance(value, str):
            return
        parsed = urllib.parse.urlsplit(value)
        endpoint_origin = normalize_mastodon_instance(
            urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        )
        if endpoint_origin != origin:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_UNSUPPORTED",
                "Die OAuth-Endpunkte dieser Instanz sind nicht sicher konfiguriert.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

    @staticmethod
    def _validate_peer_address(response: httpx.Response) -> None:
        stream = response.extensions.get("network_stream")
        if stream is None or not hasattr(stream, "get_extra_info"):
            return
        peer = stream.get_extra_info("server_addr") or stream.get_extra_info("peername")
        if not peer:
            return
        try:
            address = ipaddress.ip_address(peer[0] if isinstance(peer, tuple) else peer)
        except ValueError:
            return
        if not address.is_global:
            raise mastodon_sso_error(
                "MASTODON_INSTANCE_PRIVATE",
                "Die Mastodon-Instanz hat auf eine private Netzwerkadresse aufgelöst.",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )


class MastodonCredentialCipher:
    def __init__(self, key: str | None = None) -> None:
        configured = key or get_settings().mastodon_sso_encryption_key
        if not configured:
            raise RuntimeError("MASTODON_SSO_ENCRYPTION_KEY is not configured")
        try:
            self.fernet = Fernet(configured.encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError("MASTODON_SSO_ENCRYPTION_KEY is invalid") from exc

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Stored Mastodon SSO credentials cannot be decrypted") from exc


async def get_or_register_mastodon_app(
    session: AsyncSession,
    origin: str,
    *,
    client: MastodonSSOClient | None = None,
    cipher: MastodonCredentialCipher | None = None,
) -> MastodonAppCredentials:
    settings = get_settings()
    client = client or MastodonSSOClient(settings)
    cipher = cipher or MastodonCredentialCipher(settings.mastodon_sso_encryption_key)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:origin, 0))"),
        {"origin": origin},
    )
    record = await session.scalar(
        select(MastodonOAuthInstance)
        .where(MastodonOAuthInstance.instance_origin == origin)
        .with_for_update()
    )
    now = utcnow()
    if record and record.client_id_encrypted and record.client_secret_encrypted and record.oauth_scope:
        record.last_used_at = now
        await session.commit()
        return MastodonAppCredentials(
            origin,
            cipher.decrypt(record.client_id_encrypted),
            cipher.decrypt(record.client_secret_encrypted),
            record.oauth_scope,
        )
    if record and record.registration_retry_after and record.registration_retry_after > now:
        raise mastodon_sso_error(
            "MASTODON_APP_REGISTRATION_BACKOFF",
            "Die Anmeldung für diese Instanz kann gerade nicht vorbereitet werden. Bitte versuchen Sie es später erneut.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if record is None:
        record = MastodonOAuthInstance(instance_origin=origin)
        session.add(record)
        await session.flush()
    try:
        info = await client.validate_instance(origin)
        client_id, client_secret = await client.register_application(info)
    except HTTPException:
        record.registration_failure_count += 1
        record.registration_retry_after = now + timedelta(
            seconds=settings.mastodon_sso_registration_backoff_seconds
        )
        await session.commit()
        raise
    record.client_id_encrypted = cipher.encrypt(client_id)
    record.client_secret_encrypted = cipher.encrypt(client_secret)
    record.oauth_scope = info.scope
    record.software_version = info.version
    record.registration_failure_count = 0
    record.registration_retry_after = None
    record.last_used_at = now
    await session.commit()
    return MastodonAppCredentials(origin, client_id, client_secret, info.scope)


async def create_mastodon_oauth_flow(
    session: AsyncSession,
    instance: str,
    *,
    mode: str,
    redirect_path: str,
    user_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    origin = normalize_mastodon_instance(instance)
    credentials = await get_or_register_mastodon_app(session, origin)
    state = generate_token()
    code_verifier = generate_token()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    now = utcnow()
    await session.execute(delete(OAuthFlowGrant).where(OAuthFlowGrant.expires_at <= now))
    session.add(
        OAuthFlowGrant(
            state_hash=hash_token(state),
            provider="mastodon",
            mode=mode,
            redirect_path=safe_redirect_path(redirect_path),
            user_id=user_id,
            instance_origin=origin,
            code_verifier=code_verifier,
            expires_at=now + timedelta(seconds=settings.mastodon_sso_state_ttl_seconds),
        )
    )
    await session.commit()
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": credentials.client_id,
            "redirect_uri": oauth_redirect_uri("mastodon"),
            "scope": credentials.scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return state, f"{origin}/oauth/authorize?{query}"


async def consume_mastodon_oauth_flow(
    session: AsyncSession,
    state: str,
) -> OAuthFlowGrant | None:
    grant = await session.scalar(
        delete(OAuthFlowGrant)
        .where(
            OAuthFlowGrant.state_hash == hash_token(state),
            OAuthFlowGrant.expires_at > utcnow(),
        )
        .returning(OAuthFlowGrant)
    )
    await session.commit()
    return grant


async def exchange_mastodon_oauth_code(
    session: AsyncSession,
    grant: OAuthFlowGrant,
    code: str,
) -> OAuthIdentity:
    record = await session.scalar(
        select(MastodonOAuthInstance).where(
            MastodonOAuthInstance.instance_origin == grant.instance_origin
        )
    )
    if not record or not record.client_id_encrypted or not record.client_secret_encrypted or not record.oauth_scope:
        raise mastodon_sso_error(
            "MASTODON_APP_CREDENTIALS_MISSING",
            "Die Mastodon-Anmeldung muss neu gestartet werden.",
            status.HTTP_409_CONFLICT,
        )
    cipher = MastodonCredentialCipher()
    credentials = MastodonAppCredentials(
        grant.instance_origin,
        cipher.decrypt(record.client_id_encrypted),
        cipher.decrypt(record.client_secret_encrypted),
        record.oauth_scope,
    )
    return await MastodonSSOClient().exchange_code(
        credentials,
        code,
        grant.code_verifier,
    )

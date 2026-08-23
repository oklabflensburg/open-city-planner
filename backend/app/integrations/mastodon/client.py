from dataclasses import dataclass

import httpx

from app.observability.external import instrumented_httpx_request


@dataclass(frozen=True)
class MastodonStatus:
    id: str
    url: str | None


@dataclass(frozen=True)
class MastodonMedia:
    id: str
    url: str | None


class MastodonError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after


class MastodonClient:
    """Small HTTP-only client for the Mastodon API; contains no publication policy."""

    def __init__(self, base_url: str, access_token: str, *, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout
        self.transport = transport

    async def create_status(
        self,
        status: str,
        *,
        visibility: str,
        language: str,
        idempotency_key: str,
        media_ids: list[str] | None = None,
    ) -> MastodonStatus:
        data: dict[str, str | list[str]] = {
            "status": status,
            "visibility": visibility,
            "language": language,
        }
        if media_ids:
            data["media_ids[]"] = media_ids
        response = await self._request(
            "POST",
            "/api/v1/statuses",
            headers={"Idempotency-Key": idempotency_key},
            data=data,
        )
        payload = response.json()
        return MastodonStatus(id=str(payload["id"]), url=payload.get("url"))

    async def upload_media(
        self,
        image: bytes,
        *,
        description: str,
        filename: str = "stadtplaner.jpg",
    ) -> MastodonMedia:
        response = await self._request(
            "POST",
            "/api/v2/media",
            data={"description": description},
            files={"file": (filename, image, "image/jpeg")},
        )
        payload = response.json()
        return MastodonMedia(id=str(payload["id"]), url=payload.get("url"))

    async def verify_credentials(self) -> dict:
        response = await self._request("GET", "/api/v1/accounts/verify_credentials")
        payload = response.json()
        return {"id": str(payload["id"]), "username": payload.get("username"), "acct": payload.get("acct"), "url": payload.get("url")}

    async def max_characters(self) -> int:
        response = await self._request("GET", "/api/v2/instance", authenticated=False)
        try:
            return max(200, int(response.json()["configuration"]["statuses"]["max_characters"]))
        except (KeyError, TypeError, ValueError):
            return 500

    async def max_media_description_characters(self) -> int:
        response = await self._request("GET", "/api/v2/instance", authenticated=False)
        try:
            return max(
                100,
                int(response.json()["configuration"]["media_attachments"]["description_limit"]),
            )
        except (KeyError, TypeError, ValueError):
            return 1500

    async def _request(self, method: str, path: str, *, authenticated: bool = True, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        if authenticated:
            headers["Authorization"] = f"Bearer {self.access_token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await instrumented_httpx_request(
                    client,
                    method,
                    f"{self.base_url}{path}",
                    provider="mastodon",
                    operation=path,
                    headers=headers,
                    **kwargs,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise MastodonError("Mastodon ist vorübergehend nicht erreichbar.", retryable=True) from exc
        if response.is_success:
            return response
        retry_after = None
        if value := response.headers.get("Retry-After"):
            try:
                retry_after = max(1, int(float(value)))
            except ValueError:
                retry_after = None
        retryable = response.status_code == 429 or response.status_code >= 500
        message = "Mastodon-Anfrage fehlgeschlagen"
        try:
            error = response.json().get("error")
            if isinstance(error, str) and error.strip():
                message = error.strip()[:500]
        except (ValueError, AttributeError):
            pass
        raise MastodonError(message, status_code=response.status_code, retryable=retryable, retry_after=retry_after)

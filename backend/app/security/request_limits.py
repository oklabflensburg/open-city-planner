from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse

from app.core.config import get_settings


class RequestTooLargeError(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Enforce limits while ASGI body chunks are consumed, even without Content-Length."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http" or scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        settings = get_settings()
        path = scope.get("path", "")
        limit = (
            settings.avatar_max_file_size + settings.upload_body_overhead_bytes
            if path.endswith("/users/me/avatar")
            else settings.max_json_body_bytes
        )
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        try:
            if raw_length is not None and int(raw_length) > limit:
                await self._reject(scope, send, limit)
                return
        except ValueError:
            await self._reject(scope, send, limit)
            return
        consumed = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise RequestTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLargeError:
            await self._reject(scope, send, limit)

    @staticmethod
    async def _reject(
        scope: dict[str, Any],
        send: Callable[[dict[str, Any]], Awaitable[None]],
        limit: int,
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": {
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": "Der Anfrageinhalt ist zu groß.",
                        "max_bytes": limit,
                    }
                }
            },
        )
        await response(scope, lambda: None, send)

import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def validate_csrf(request: Request) -> None:
    if request.method.upper() not in UNSAFE_METHODS:
        return
    settings = get_settings()
    cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
    header_token = request.headers.get("x-csrf-token")
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "CSRF_FAILED",
                    "message": "Die Sicherheitsprüfung ist fehlgeschlagen.",
                }
            },
        )


def validate_refresh_origin(request: Request) -> None:
    """Protect cookie-based refresh without requiring a JS-readable token after reload."""
    origin = request.headers.get("origin")
    settings = get_settings()
    allowed = {value.rstrip("/") for value in settings.cors_origin_list}
    allowed.add(settings.app_base_url.rstrip("/"))
    candidate = origin.rstrip("/") if origin else ""
    if not candidate:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            candidate = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if not candidate and not settings.refresh_require_origin and not settings.production:
        return
    if candidate not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "CSRF_FAILED",
                    "message": "Die Sicherheitsprüfung ist fehlgeschlagen.",
                }
            },
        )

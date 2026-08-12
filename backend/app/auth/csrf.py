import secrets

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
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "CSRF_FAILED", "message": "Die Sicherheitsprüfung ist fehlgeschlagen."}},
        )

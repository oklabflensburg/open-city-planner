from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.rate_limit import check_rate_limit, rate_limit_key


def is_statement_timeout_error(error: BaseException) -> bool:
    """Erkennt PostgreSQL query_canceled (SQLSTATE 57014) ohne Fehlermeldung auszuwerten."""
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if (
            getattr(current, "sqlstate", None) == "57014"
            or getattr(current, "pgcode", None) == "57014"
        ):
            return True
        for attribute in ("orig", "__cause__", "__context__"):
            nested = getattr(current, attribute, None)
            if isinstance(nested, BaseException):
                pending.append(nested)
    return False


async def guard_public_query(request: Request, session: AsyncSession, resource: str) -> None:
    settings = get_settings()
    await check_rate_limit(
        rate_limit_key(request, f"public-query:{resource}"),
        attempts=settings.public_query_rate_limit_attempts,
        window_seconds=settings.public_query_rate_limit_window_seconds,
        code="PUBLIC_QUERY_RATE_LIMITED",
        message="Zu viele Analyseabfragen. Bitte kurz warten.",
    )
    await session.execute(
        text("SELECT set_config('statement_timeout', :timeout, true)"),
        {"timeout": f"{settings.public_query_timeout_ms}ms"},
    )

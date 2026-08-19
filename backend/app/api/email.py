from fastapi import APIRouter, Query, Request

from app.auth.dependencies import SessionDep
from app.schemas.admin import EmailUnsubscribeRead
from app.services.email_unsubscribe import unsubscribe_newsletter
from app.services.rate_limit import check_rate_limit, rate_limit_key

router = APIRouter(prefix="/email", tags=["Notifications"])
MESSAGE = "Sie erhalten künftig keine freiwilligen Newsletter-E-Mails mehr."


@router.post("/unsubscribe", response_model=EmailUnsubscribeRead)
async def post_email_unsubscribe(
    request: Request,
    session: SessionDep,
    token: str | None = Query(default=None, min_length=20, max_length=512),
) -> EmailUnsubscribeRead:
    await check_rate_limit(rate_limit_key(request, "email-unsubscribe"), attempts=20)
    if token:
        await unsubscribe_newsletter(session, token)
    return EmailUnsubscribeRead(success=True, message=MESSAGE)

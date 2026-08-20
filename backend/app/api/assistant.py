from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.assistant import AssistantQueryRequest, AssistantQueryResponse
from app.services.assistant import answer_assistant_query
from app.services.assistant_provider import get_assistant_provider
from app.services.assistant_tools import AssistantToolError
from app.services.public_query_security import guard_public_query, is_statement_timeout_error

router = APIRouter(prefix="/assistant", tags=["Assistant"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/query",
    response_model=AssistantQueryResponse,
    summary="Kontrollierten read-only Stadtplaner-Assistenten ausführen",
    description=(
        "Kombiniert höchstens vier explizit freigegebene öffentliche Leseoperationen. "
        "Der Endpunkt kann keine administrativen oder schreibenden Aktionen ausführen."
    ),
)
async def assistant_query(
    payload: AssistantQueryRequest,
    request: Request,
    session: SessionDep,
) -> AssistantQueryResponse:
    try:
        await guard_public_query(request, session, "assistant")
        return await answer_assistant_query(
            session, payload, provider=get_assistant_provider()
        )
    except AssistantToolError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"error": {"code": error.code, "message": error.message}},
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "INVALID_TOOL_ARGUMENTS", "message": "Ungültige Tool-Argumente."}},
        ) from error
    except DBAPIError as error:
        if not is_statement_timeout_error(error):
            raise
        await session.rollback()
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "ASSISTANT_QUERY_TIMEOUT", "message": "Die Anfrage konnte nicht rechtzeitig abgeschlossen werden."}},
        ) from error

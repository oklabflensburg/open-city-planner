from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.search import SearchInterpretResponse, SearchRequest, SearchResponse
from app.services.public_query_security import guard_public_query, is_statement_timeout_error
from app.services.search_executor import SearchExecutionError, execute_search
from app.services.search_interpreter import SearchInterpretationError, interpret_search

router = APIRouter(prefix="/search", tags=["Search"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _search_error(error: SearchInterpretationError | SearchExecutionError) -> NoReturn:
    raise HTTPException(
        status_code=error.status_code,
        detail={"error": {"code": error.code, "message": error.message}},
    ) from error


async def _prepare_search(request: Request, session: AsyncSession) -> None:
    try:
        await guard_public_query(request, session, "search")
    except DBAPIError as error:
        if not is_statement_timeout_error(error):
            raise
        await session.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SEARCH_QUERY_TIMEOUT",
                    "message": "Die Suche konnte nicht rechtzeitig abgeschlossen werden.",
                }
            },
        ) from error


@router.post(
    "/interpret",
    response_model=SearchInterpretResponse,
    summary="Natürlichsprachliche Suche in einen sicheren Suchplan übersetzen",
)
async def interpret(
    payload: SearchRequest, request: Request, session: SessionDep
) -> SearchInterpretResponse:
    await _prepare_search(request, session)
    try:
        plan = await interpret_search(session, payload.query)
    except SearchInterpretationError as error:
        _search_error(error)
    return SearchInterpretResponse(query=payload.query, plan=plan)


@router.post(
    "",
    response_model=SearchResponse,
    summary="Natürlichsprachliche Suche sicher ausführen",
)
async def search(
    payload: SearchRequest, request: Request, session: SessionDep
) -> SearchResponse:
    await _prepare_search(request, session)
    try:
        plan = await interpret_search(session, payload.query)
        return await execute_search(session, payload.query, plan)
    except (SearchInterpretationError, SearchExecutionError) as error:
        _search_error(error)

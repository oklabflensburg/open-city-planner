import logging

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

if settings.configured_oauth_providers:
    logger.info("Enabled OAuth providers: %s", ", ".join(settings.configured_oauth_providers))
else:
    logger.info("No OAuth providers enabled; OAuth buttons will remain hidden")

app = FastAPI(title="Open City Map API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

app.include_router(api_router)


@app.exception_handler(RequestValidationError)
async def validation_error_response(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    if request.url.path == "/api/v1/contact":
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "error": {
                        "code": "CONTACT_VALIDATION_FAILED",
                        "message": "Bitte prüfen Sie die eingegebenen Kontaktdaten.",
                    }
                }
            },
        )
    return await request_validation_exception_handler(request, exc)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return response


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

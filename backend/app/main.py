import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.cache.redis import close_redis, initialize_redis, redis_health
from app.core.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

if settings.configured_oauth_providers:
    logger.info("Enabled OAuth providers: %s", ", ".join(settings.configured_oauth_providers))
else:
    logger.info("No OAuth providers enabled; OAuth buttons will remain hidden")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await initialize_redis()
    try:
        yield
    finally:
        await close_redis()


OPENAPI_TAGS = [
    {"name": "Analysis Areas", "description": "Öffentliche Gemeinde-, Stadtteil- und Quartiersdaten mit räumlichen Aggregationen."},
    {"name": "Analytics", "description": "Kennzahlen, Benchmarks und Zeitreihen des Stadtplaners."},
    {"name": "Polygons", "description": "Öffentliche Verkaufsflächen sowie berechtigungsgeschützte Pflegeoperationen."},
    {"name": "OpenStreetMap", "description": "Lokale OSM-Referenzdaten für Viewports, POIs und Flächenobjekte."},
    {"name": "Authentication", "description": "Cookie-basierte Anmeldung, Sitzungen, OAuth und CSRF-geschützte Änderungen."},
    {"name": "Users", "description": "Profil und benutzerbezogene Ressourcen."},
    {"name": "Administration", "description": "Rollen- und Verwaltungsfunktionen für berechtigte Konten."},
    {"name": "Contact", "description": "Öffentliches, rate-limitiertes Kontaktformular."},
    {"name": "Media", "description": "Öffentlich abrufbare, serverseitig normalisierte Medien."},
]

app = FastAPI(
    title="Stadtplaner API",
    description=(
        "Öffentliche GIS- und Analyse-API für Verkaufsflächen, räumliche Analysegebiete "
        "und lokale OpenStreetMap-Referenzdaten. Schreiboperationen verwenden sichere "
        "HttpOnly-Cookies und CSRF-Schutz; Verwaltungsdaten sind rollenbeschränkt."
    ),
    version=settings.api_version,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1_000, compresslevel=5)

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
    return {"status": "ok", "database": "ok", "redis": await redis_health()}

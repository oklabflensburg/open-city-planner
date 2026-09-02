import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from ipaddress import ip_address

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import Response as FastAPIResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.router import api_router
from app.auth.module_sdk import HostPermissionDependencies
from app.cache.redis import close_redis, initialize_redis, redis_health
from app.core.config import BACKEND_ENV_FILE, get_settings
from app.db.session import AsyncSessionLocal, database_health, engine
from app.integrations.module_host_ports import (
    HostCacheGenerations,
    HostMapPreviews,
    HostModuleCache,
    HostModuleHttpClientFactory,
    HostOsmSnapshotQueries,
    HostPolygonAnalytics,
    HostPolygonIdentities,
    HostPolygonQueries,
    HostPolygonSpatialMatches,
    HostPublicQueries,
    HostStatisticsQueries,
)
from app.models.user import User
from app.observability.logging import configure_logging
from app.observability.metrics import REDIS_AVAILABLE, REGISTRY, set_build_info
from app.observability.middleware import ObservabilityMiddleware
from app.observability.tracing import configure_tracing
from app.platform.events import InProcessEventBus
from app.platform.modules import (
    EntryPointModuleDiscovery,
    FirstPartyModuleDiscovery,
    activate_enabled_module_python_paths,
    create_module_runtime,
)
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.permissions import (
    LegacyRolePermissionResolver,
    PermissionEngine,
    PermissionRegistry,
)
from app.platform.modules.persistence import HostDatabaseSessionProvider
from app.platform.modules.sdk import PermissionDefinition
from app.security.request_limits import RequestBodyLimitMiddleware
from app.services.map_previews import MapPreviewError, map_preview_service

settings = get_settings()
event_bus = InProcessEventBus()
permission_registry = PermissionRegistry()
for definition in (
    PermissionDefinition(
        id="platform.superuser",
        module_id="platform",
        description="Universeller administrativer Plattformzugriff",
        category="platform",
    ),
    PermissionDefinition(
        id="platform.verwaltung",
        module_id="platform",
        description="Bestehende Verwaltungsrolle verwenden",
        category="platform",
    ),
):
    if definition.module_id == "platform":
        permission_registry.register_platform(definition)
    else:
        permission_registry.register(definition)
permission_engine = PermissionEngine(
    permission_registry,
    LegacyRolePermissionResolver({"VERWALTUNG": ("platform.verwaltung",)}),
)


async def load_permission_subject(principal_id: str) -> User | None:
    try:
        user_id = uuid.UUID(principal_id)
    except ValueError:
        return None
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        return user if user is not None and user.is_active else None


module_runtime = create_module_runtime(
    enabled_module_ids=settings.enabled_module_list,
    discovery_providers=(
        FirstPartyModuleDiscovery(
            excluded_module_ids=settings.excluded_builtin_module_list
        ),
        EntryPointModuleDiscovery(),
    ),
    host_version=settings.api_version,
    context_factory=ModuleContextFactory(
        ModuleHostServices(
            database=HostDatabaseSessionProvider(),
            permission_dependencies=HostPermissionDependencies(),
            cache_factory=HostModuleCache,
            cache_generations=HostCacheGenerations(),
            public_queries=HostPublicQueries(settings),
            map_previews=HostMapPreviews(),
            http=HostModuleHttpClientFactory(settings=settings),
            polygons=HostPolygonQueries(),
            polygon_analytics=HostPolygonAnalytics(),
            statistics=HostStatisticsQueries(),
            osm_snapshots=HostOsmSnapshotQueries(),
            polygon_spatial_matches=HostPolygonSpatialMatches(),
            polygon_identities=HostPolygonIdentities(),
        ),
        event_bus=event_bus,
        permission_engine=permission_engine,
        permission_subject_loader=load_permission_subject,
        module_env_file=BACKEND_ENV_FILE,
    ),
    permission_registry=permission_registry,
)
activate_enabled_module_python_paths()
configure_logging(
    level=settings.log_level,
    service="stadtplaner-api",
    environment=settings.app_environment,
    release_sha=settings.release_sha,
    json_logs=settings.log_format == "json",
)
logger = logging.getLogger(__name__)
set_build_info(
    release_sha=settings.release_sha,
    version=settings.api_version,
    environment=settings.app_environment,
)

if settings.configured_oauth_providers:
    logger.info("Enabled OAuth providers: %s", ", ".join(settings.configured_oauth_providers))
else:
    logger.info("No OAuth providers enabled; OAuth buttons will remain hidden")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await initialize_redis()
    try:
        await module_runtime.startup()
        yield
    finally:
        try:
            await module_runtime.shutdown()
        finally:
            await close_redis()
            tracing_runtime.shutdown()


OPENAPI_TAGS = [
    {
        "name": "Polygons",
        "description": "Öffentliche Verkaufsflächen sowie berechtigungsgeschützte Pflegeoperationen.",
    },
    {
        "name": "OpenStreetMap",
        "description": "Lokale OSM-Referenzdaten für Viewports, POIs und Flächenobjekte.",
    },
    {
        "name": "Authentication",
        "description": "Cookie-basierte Anmeldung, Sitzungen, OAuth und CSRF-geschützte Änderungen.",
    },
    {"name": "Users", "description": "Profil und benutzerbezogene Ressourcen."},
    {
        "name": "Administration",
        "description": "Rollen- und Verwaltungsfunktionen für berechtigte Konten.",
    },
    {"name": "Contact", "description": "Öffentliches, rate-limitiertes Kontaktformular."},
    {"name": "Media", "description": "Öffentlich abrufbare, serverseitig normalisierte Medien."},
    {
        "name": "Notifications",
        "description": "Persönliche, persistente Benachrichtigungen, Präferenzen, Abonnements und Realtime-Auslieferung.",
    },
]

app = FastAPI(
    title="Stadtplaner API",
    description=(
        "Öffentliche GIS- und Analyse-API für Verkaufsflächen und lokale "
        "OpenStreetMap-Referenzdaten. Schreiboperationen verwenden sichere "
        "HttpOnly-Cookies und CSRF-Schutz; Verwaltungsdaten sind rollenbeschränkt."
    ),
    version=settings.api_version,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.state.permission_engine = permission_engine
app.state.module_runtime = module_runtime

app.add_middleware(GZipMiddleware, minimum_size=1_000, compresslevel=5)
app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(
    ObservabilityMiddleware,
    metrics_enabled=settings.metrics_enabled,
    metrics_path=settings.metrics_path,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

app.include_router(api_router)
module_runtime.register(app)
event_bus.seal()


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
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    csp = "default-src 'none'; frame-ancestors 'none'"
    if request.url.path in {"/docs", "/redoc"}:
        csp = (
            "default-src 'none'; frame-ancestors 'none'; "
            "connect-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com"
        )
    response.headers.setdefault("Content-Security-Policy", csp)
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), microphone=(), camera=(), "
        "publickey-credentials-create=(self), publickey-credentials-get=(self)",
    )
    if settings.production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    if request.url.path.startswith(
        ("/api/v1/auth", "/api/v1/users", "/api/v1/admin", "/api/v1/notifications")
    ):
        response.headers.setdefault("Cache-Control", "private, no-store")
    return response


async def health_status() -> tuple[bool, dict[str, str]]:
    database = await database_health()
    redis = await redis_health()
    REDIS_AVAILABLE.set(1 if redis == "ok" else 0)

    database_ok = database == "ok"
    redis_ok = True
    if settings.redis_required:
        redis_ok = redis == "ok"
    elif settings.redis_enabled:
        redis_ok = redis in {"ok", "degraded", "disabled"}
    elif settings.redis_required:
        redis_ok = False

    ready = database_ok and redis_ok
    payload = {"status": "ok" if ready else "not_ready", "database": database, "redis": redis}
    return ready, payload


@app.get("/health/live", tags=["health"])
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready() -> Response:
    ready, payload = await health_status()
    if ready:
        return JSONResponse(status_code=200, content=payload)
    return JSONResponse(status_code=503, content=payload)


@app.get("/health", tags=["health"])
async def health() -> Response:
    return await health_ready()


@app.get("/health/info", tags=["health"])
async def health_info() -> dict[str, str]:
    return {
        "version": settings.api_version,
        "release_sha": settings.release_sha,
        "environment": settings.app_environment,
    }


@app.get("/health/map-preview.webp", include_in_schema=False)
async def health_map_preview(request: Request) -> Response:
    client_host = request.client.host if request.client else ""
    try:
        local_client = ip_address(client_host).is_loopback
    except ValueError:
        local_client = False
    if not local_client:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    try:
        image = await map_preview_service.renderer.render(
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [[9.43, 54.78], [9.431, 54.78], [9.431, 54.781], [9.43, 54.78]]
                ],
            },
            bbox=(9.429, 54.779, 9.432, 54.782),
            width=320,
            height=180,
            category=None,
            feature_kind="area",
        )
    except MapPreviewError:
        return JSONResponse(status_code=503, content={"status": "renderer_unavailable"})
    return Response(
        content=image,
        media_type="image/webp",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


if settings.metrics_enabled:

    @app.get(settings.metrics_path, include_in_schema=False)
    async def metrics() -> FastAPIResponse:
        return FastAPIResponse(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


tracing_runtime = configure_tracing(app, engine, settings)

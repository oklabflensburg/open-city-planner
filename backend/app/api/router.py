from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.analysis_areas import router as analysis_areas_router
from app.api.analytics import router as analytics_router
from app.api.assistant import router as assistant_router
from app.api.auth import router as auth_router
from app.api.contact import router as contact_router
from app.api.data_sources import router as data_sources_router
from app.api.email import router as email_router
from app.api.media import router as media_router
from app.api.notifications import router as notifications_router
from app.api.osm import router as osm_router
from app.api.polygons import router as polygon_router
from app.api.search import router as search_router
from app.api.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(admin_router)
api_router.include_router(analysis_areas_router)
api_router.include_router(assistant_router)
api_router.include_router(data_sources_router)
api_router.include_router(analytics_router)
api_router.include_router(auth_router)
api_router.include_router(contact_router)
api_router.include_router(media_router)
api_router.include_router(notifications_router)
api_router.include_router(email_router)
api_router.include_router(osm_router)
api_router.include_router(polygon_router)
api_router.include_router(search_router)
api_router.include_router(users_router)

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.media import router as media_router
from app.api.polygons import router as polygon_router
from app.api.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(media_router)
api_router.include_router(polygon_router)
api_router.include_router(users_router)

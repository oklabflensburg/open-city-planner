from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.avatar_service import avatar_storage_dir

router = APIRouter(prefix="/media", tags=["Media"])


@router.get("/avatars/{filename}")
async def get_avatar(filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or not filename.endswith(".webp"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    path = avatar_storage_dir() / filename
    try:
        path.relative_to(avatar_storage_dir())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    if not Path(path).is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

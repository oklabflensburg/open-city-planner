import io
import logging
import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
AVATAR_ROUTE_PREFIX = "/api/v1/media/avatars"
MIN_AVATAR_DIMENSION = 128
MAX_AVATAR_DIMENSION = 6000
Image.MAX_IMAGE_PIXELS = MAX_AVATAR_DIMENSION * MAX_AVATAR_DIMENSION


def avatar_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


def avatar_storage_dir(settings: Settings | None = None) -> Path:
    active_settings = settings or get_settings()
    directory = Path(active_settings.avatar_upload_dir).expanduser()
    if not directory.is_absolute():
        directory = Path.cwd() / directory
    return directory / "avatars"


async def save_avatar(upload: UploadFile, user_id: object, settings: Settings | None = None) -> str:
    active_settings = settings or get_settings()
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        logger.info("Avatar upload rejected for user %s: invalid content type", user_id)
        raise avatar_error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "INVALID_AVATAR_TYPE", "Bitte laden Sie ein JPG-, PNG- oder WebP-Bild hoch.")

    raw = await _read_limited(upload, active_settings.avatar_max_file_size, user_id)
    image = _decode_image(raw, user_id)
    output = _normalize_image(image, active_settings.avatar_output_size, user_id)

    directory = avatar_storage_dir(active_settings)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_urlsafe(24)}.webp"
    path = directory / filename
    try:
        output.save(path, format="WEBP", quality=active_settings.avatar_webp_quality, method=6)
    except OSError as exc:
        logger.exception("Avatar upload failed while saving for user %s", user_id)
        raise avatar_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "AVATAR_UPLOAD_FAILED", "Das Profilbild konnte nicht gespeichert werden.") from exc

    logger.info("Avatar upload stored for user %s", user_id)
    return build_avatar_url(filename, active_settings)


def build_avatar_url(filename: str, settings: Settings | None = None) -> str:
    active_settings = settings or get_settings()
    path = f"{AVATAR_ROUTE_PREFIX}/{filename}"
    if active_settings.media_base_url:
        return f"{active_settings.media_base_url.rstrip('/')}{path}"
    return path


def local_avatar_path(avatar_url: str | None, settings: Settings | None = None) -> Path | None:
    if not avatar_url:
        return None
    parsed_path = urlparse(avatar_url).path
    prefix = f"{AVATAR_ROUTE_PREFIX}/"
    if not parsed_path.startswith(prefix):
        return None
    filename = parsed_path.removeprefix(prefix)
    if "/" in filename or not filename.endswith(".webp"):
        return None
    return avatar_storage_dir(settings) / filename


def delete_avatar_file(avatar_url: str | None, settings: Settings | None = None) -> None:
    path = local_avatar_path(avatar_url, settings)
    if not path:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Avatar file could not be deleted: %s", path)


def _decode_image(raw: bytes, user_id: object) -> Image.Image:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format not in ALLOWED_FORMATS:
                logger.info("Avatar upload rejected for user %s: invalid image format", user_id)
                raise avatar_error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "INVALID_AVATAR_TYPE", "Bitte laden Sie ein JPG-, PNG- oder WebP-Bild hoch.")
            width, height = image.size
            if width < MIN_AVATAR_DIMENSION or height < MIN_AVATAR_DIMENSION:
                raise avatar_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_AVATAR_IMAGE", "Das Bild muss mindestens 128 x 128 Pixel groß sein.")
            if width > MAX_AVATAR_DIMENSION or height > MAX_AVATAR_DIMENSION:
                raise avatar_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_AVATAR_IMAGE", "Das Bild ist zu groß.")
            return image.copy()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        logger.info("Avatar upload rejected for user %s: invalid image bytes", user_id)
        raise avatar_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_AVATAR_IMAGE", "Die Datei ist kein gültiges Bild.") from exc


def _normalize_image(image: Image.Image, output_size: int, user_id: object) -> Image.Image:
    try:
        transposed = ImageOps.exif_transpose(image)
        square = ImageOps.fit(transposed, (output_size, output_size), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        if square.mode in {"RGBA", "LA"} or (square.mode == "P" and "transparency" in square.info):
            background = Image.new("RGB", square.size, (255, 255, 255))
            background.paste(square.convert("RGBA"), mask=square.convert("RGBA").getchannel("A"))
            return background
        return square.convert("RGB")
    except OSError as exc:
        logger.exception("Avatar processing failed for user %s", user_id)
        raise avatar_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "AVATAR_PROCESSING_FAILED", "Das Bild konnte nicht verarbeitet werden.") from exc


async def _read_limited(upload: UploadFile, max_size: int, user_id: object) -> bytes:
    raw = await upload.read(max_size + 1)
    if len(raw) > max_size:
        logger.info("Avatar upload rejected for user %s: file too large", user_id)
        raise avatar_error(status.HTTP_413_CONTENT_TOO_LARGE, "AVATAR_TOO_LARGE", "Das Profilbild darf maximal 5 MB groß sein.")
    if not raw:
        raise avatar_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_AVATAR_IMAGE", "Die Datei ist leer.")
    return raw

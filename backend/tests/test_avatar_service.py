import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.core.config import Settings
from app.services.avatar_service import (
    build_avatar_url,
    delete_avatar_file,
    local_avatar_path,
    save_avatar,
)


def upload_file(raw: bytes, content_type: str, filename: str = "avatar.png") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(raw),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def image_bytes(format_name: str, size: tuple[int, int] = (320, 240), exif: bytes | None = None) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, (24, 92, 132)).save(output, format=format_name, exif=exif or b"")
    return output.getvalue()


def avatar_settings(tmp_path: Path, **overrides: object) -> Settings:
    values = {
        "avatar_upload_dir": str(tmp_path),
        "avatar_max_file_size": 5_242_880,
        "avatar_output_size": 512,
        "avatar_webp_quality": 85,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("format_name", "content_type", "filename"),
    [
        ("JPEG", "image/jpeg", "avatar.jpg"),
        ("PNG", "image/png", "avatar.png"),
        ("WEBP", "image/webp", "avatar.webp"),
    ],
)
async def test_save_avatar_normalizes_supported_images(tmp_path: Path, format_name: str, content_type: str, filename: str) -> None:
    settings = avatar_settings(tmp_path)

    avatar_url = await save_avatar(upload_file(image_bytes(format_name), content_type, filename), "user-1", settings)
    path = local_avatar_path(avatar_url, settings)

    assert avatar_url.startswith("/api/v1/media/avatars/")
    assert avatar_url.endswith(".webp")
    assert path is not None
    assert path.is_file()
    with Image.open(path) as saved:
        assert saved.format == "WEBP"
        assert saved.size == (512, 512)
        assert saved.mode == "RGB"
        assert not saved.getexif()


async def test_save_avatar_rejects_invalid_mime(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await save_avatar(upload_file(image_bytes("PNG"), "text/plain"), "user-1", settings)

    assert exc.value.status_code == 415
    assert exc.value.detail["error"]["code"] == "INVALID_AVATAR_TYPE"


async def test_save_avatar_rejects_fake_jpeg(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await save_avatar(upload_file(b"not an image", "image/jpeg", "avatar.jpg"), "user-1", settings)

    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "INVALID_AVATAR_IMAGE"


async def test_save_avatar_rejects_svg(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"></svg>'

    with pytest.raises(HTTPException) as exc:
        await save_avatar(upload_file(svg, "image/svg+xml", "avatar.svg"), "user-1", settings)

    assert exc.value.status_code == 415
    assert exc.value.detail["error"]["code"] == "INVALID_AVATAR_TYPE"


async def test_save_avatar_rejects_too_large_file(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path, avatar_max_file_size=8)

    with pytest.raises(HTTPException) as exc:
        await save_avatar(upload_file(b"012345678", "image/png"), "user-1", settings)

    assert exc.value.status_code == 413
    assert exc.value.detail["error"]["code"] == "AVATAR_TOO_LARGE"


async def test_save_avatar_rejects_small_dimensions(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await save_avatar(upload_file(image_bytes("PNG", (80, 80)), "image/png"), "user-1", settings)

    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "INVALID_AVATAR_IMAGE"


async def test_avatar_filename_is_random_and_delete_removes_file(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path)

    first_url = await save_avatar(upload_file(image_bytes("PNG"), "image/png"), "user-1", settings)
    second_url = await save_avatar(upload_file(image_bytes("PNG"), "image/png"), "user-1", settings)
    first_path = local_avatar_path(first_url, settings)

    assert first_url != second_url
    assert first_path is not None and first_path.is_file()

    delete_avatar_file(first_url, settings)

    assert not first_path.exists()


def test_avatar_url_does_not_duplicate_legacy_media_base_path(tmp_path: Path) -> None:
    settings = avatar_settings(
        tmp_path,
        media_base_url="https://api.example.org/media",
    )

    assert build_avatar_url("avatar.webp", settings) == (
        "https://api.example.org/api/v1/media/avatars/avatar.webp"
    )


def test_local_avatar_path_accepts_legacy_duplicated_media_url(tmp_path: Path) -> None:
    settings = avatar_settings(tmp_path)

    path = local_avatar_path(
        "https://api.example.org/media/api/v1/media/avatars/avatar.webp",
        settings,
    )

    assert path == tmp_path / "avatars" / "avatar.webp"

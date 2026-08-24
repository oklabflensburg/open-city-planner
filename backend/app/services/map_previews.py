import asyncio
import hashlib
import os
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.observability.external import instrumented_httpx_request

ALLOWED_PREVIEW_SIZES = frozenset({(320, 180), (640, 360), (800, 450), (1200, 630)})
MAX_RENDER_BYTES = 8 * 1024 * 1024


def _is_webp(body: bytes) -> bool:
    return len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP"


class MapPreviewError(RuntimeError):
    pass


class MapPreviewRenderer(ABC):
    @abstractmethod
    async def render(
        self,
        *,
        geometry: dict[str, Any],
        bbox: tuple[float, float, float, float],
        width: int,
        height: int,
        category: str | None,
        feature_kind: str,
    ) -> bytes: ...


class NativeMapPreviewRenderer(MapPreviewRenderer):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def render(
        self,
        *,
        geometry: dict[str, Any],
        bbox: tuple[float, float, float, float],
        width: int,
        height: int,
        category: str | None,
        feature_kind: str,
    ) -> bytes:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.map_preview_renderer_timeout_seconds,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            ) as client:
                response = await instrumented_httpx_request(
                    client,
                    "POST",
                    f"{self.settings.map_preview_renderer_url.rstrip('/')}/render",
                    provider="maplibre-native",
                    operation="render-preview",
                    json={
                        "geometry": geometry,
                        "bbox": bbox,
                        "width": width,
                        "height": height,
                        "category": category,
                        "featureKind": feature_kind,
                    },
                )
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            raise MapPreviewError("Der interne Kartendienst ist nicht verfügbar.") from exc
        body = response.content
        if response.headers.get("content-type", "").split(";", 1)[0] != "image/webp":
            raise MapPreviewError("Der interne Kartendienst lieferte kein WebP-Bild.")
        if not _is_webp(body) or len(body) > MAX_RENDER_BYTES:
            raise MapPreviewError("Der interne Kartendienst lieferte eine ungültige Bildgröße.")
        return body


@dataclass(frozen=True)
class MapPreview:
    body: bytes
    etag: str
    cache_hit: bool


class MapPreviewService:
    def __init__(
        self,
        settings: Settings | None = None,
        renderer: MapPreviewRenderer | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.renderer = renderer or NativeMapPreviewRenderer(self.settings)
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    def _style_hash(self) -> str:
        configured_hash = getattr(self.settings, "map_preview_style_hash", None)
        if configured_hash:
            return configured_hash
        try:
            return hashlib.sha256(Path(self.settings.map_preview_style_path).read_bytes()).hexdigest()
        except OSError as exc:
            raise MapPreviewError("Der Kartenstil ist nicht verfügbar.") from exc

    async def get(
        self,
        *,
        slug: str,
        updated_at: datetime,
        geometry: dict[str, Any],
        bbox: tuple[float, float, float, float],
        width: int,
        height: int,
        category: str | None,
        feature_kind: str,
    ) -> MapPreview:
        if (width, height) not in ALLOWED_PREVIEW_SIZES:
            raise ValueError("Nicht unterstützte Vorschaugröße.")
        if feature_kind not in {"polygon", "area"}:
            raise ValueError("Nicht unterstützter Vorschautyp.")
        cache_key = "\0".join(
            (slug, updated_at.isoformat(), self._style_hash(), str(width), str(height))
        )
        digest = hashlib.sha256(cache_key.encode()).hexdigest()
        etag = f'"{digest}"'
        cache_path = (
            Path(self.settings.map_preview_cache_dir)
            / feature_kind
            / digest[:2]
            / f"{digest}.webp"
        )
        try:
            cached = cache_path.read_bytes()
        except FileNotFoundError:
            cached = b""
        if _is_webp(cached):
            return MapPreview(cached, etag, True)

        lock = self._locks.setdefault(digest, asyncio.Lock())
        async with lock:
            try:
                cached = cache_path.read_bytes()
            except FileNotFoundError:
                cached = b""
            if _is_webp(cached):
                return MapPreview(cached, etag, True)
            rendered = await self.renderer.render(
                geometry=geometry,
                bbox=bbox,
                width=width,
                height=height,
                category=category,
                feature_kind=feature_kind,
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
            temporary = cache_path.with_suffix(f".{os.getpid()}.partial")
            try:
                with temporary.open("wb") as output:
                    output.write(rendered)
                    output.flush()
                    os.fsync(output.fileno())
                temporary.chmod(0o640)
                temporary.replace(cache_path)
                directory_fd = os.open(cache_path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                temporary.unlink(missing_ok=True)
            return MapPreview(rendered, etag, False)


map_preview_service = MapPreviewService()

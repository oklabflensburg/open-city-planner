from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.api.polygons as polygon_api
from app.schemas.polygon_directory import PolygonDirectoryItem
from app.services.map_previews import (
    MapPreview,
    MapPreviewRenderer,
    MapPreviewService,
    NativeMapPreviewRenderer,
)
from app.services.polygon_directory import DIRECTORY_SQL, polygon_directory_page

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]],
}


class RecordingRenderer(MapPreviewRenderer):
    def __init__(self) -> None:
        self.calls = 0
        self.sizes: list[tuple[int, int]] = []

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
        self.calls += 1
        self.sizes.append((width, height))
        assert geometry == GEOMETRY
        assert bbox == (9.43, 54.78, 9.44, 54.79)
        assert category == "food"
        assert feature_kind == "polygon"
        return b"RIFFxxxxWEBP"


@pytest.mark.asyncio
async def test_preview_cache_uses_updated_at_style_and_dimensions(tmp_path) -> None:
    style = tmp_path / "style.json"
    style.write_text('{"version":8}', encoding="utf-8")
    settings = SimpleNamespace(
        map_preview_style_path=str(style),
        map_preview_cache_dir=str(tmp_path / "cache"),
    )
    renderer = RecordingRenderer()
    service = MapPreviewService(settings, renderer)
    updated_at = datetime(2026, 8, 24, tzinfo=UTC)
    arguments = {
        "slug": "testflaeche",
        "updated_at": updated_at,
        "geometry": GEOMETRY,
        "bbox": (9.43, 54.78, 9.44, 54.79),
        "width": 640,
        "height": 360,
        "category": "food",
        "feature_kind": "polygon",
    }

    first = await service.get(**arguments)
    second = await service.get(**arguments)
    changed = await service.get(**{**arguments, "updated_at": updated_at + timedelta(seconds=1)})
    style.write_text('{"version":8,"name":"changed"}', encoding="utf-8")
    changed_style = await service.get(**arguments)
    social_card = await service.get(**{**arguments, "width": 1200, "height": 630})

    assert first.body == b"RIFFxxxxWEBP"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.etag == first.etag
    assert changed.etag != first.etag
    assert changed_style.etag != first.etag
    assert social_card.etag != changed_style.etag
    assert renderer.calls == 4
    assert renderer.sizes == [(640, 360), (640, 360), (640, 360), (1200, 630)]
    assert not list((tmp_path / "cache").rglob("*.partial"))


def test_preview_service_uses_native_renderer_by_default(tmp_path) -> None:
    settings = SimpleNamespace(
        map_preview_style_path=str(tmp_path / "style.json"),
        map_preview_cache_dir=str(tmp_path / "cache"),
    )

    assert isinstance(MapPreviewService(settings).renderer, NativeMapPreviewRenderer)


@pytest.mark.asyncio
async def test_preview_cache_uses_deployed_style_hash_without_reading_style(tmp_path) -> None:
    settings = SimpleNamespace(
        map_preview_style_path=str(tmp_path / "missing-style.json"),
        map_preview_style_hash="a" * 64,
        map_preview_cache_dir=str(tmp_path / "cache"),
    )
    renderer = RecordingRenderer()
    preview = await MapPreviewService(settings, renderer).get(
        slug="testflaeche",
        updated_at=datetime(2026, 8, 24, tzinfo=UTC),
        geometry=GEOMETRY,
        bbox=(9.43, 54.78, 9.44, 54.79),
        width=640,
        height=360,
        category="food",
        feature_kind="polygon",
    )
    assert preview.etag
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_preview_rejects_arbitrary_dimensions(tmp_path) -> None:
    style = tmp_path / "style.json"
    style.write_text('{"version":8}', encoding="utf-8")
    service = MapPreviewService(
        SimpleNamespace(
            map_preview_style_path=str(style),
            map_preview_cache_dir=str(tmp_path / "cache"),
        ),
        RecordingRenderer(),
    )
    with pytest.raises(ValueError, match="Vorschaugröße"):
        await service.get(
            slug="test",
            updated_at=datetime.now(UTC),
            geometry=GEOMETRY,
            bbox=(9.43, 54.78, 9.44, 54.79),
            width=641,
            height=360,
            category="food",
            feature_kind="polygon",
        )


def test_directory_item_has_no_geometry_or_private_fields() -> None:
    fields = set(PolygonDirectoryItem.model_fields)
    assert "geometry" not in fields
    assert not fields.intersection({"owner_name", "price_per_sqm", "user_id", "properties"})
    assert "geometry" not in str(DIRECTORY_SQL).lower()


@pytest.mark.asyncio
async def test_directory_page_exposes_a_next_offset() -> None:
    class Result:
        def __init__(self, value: object) -> None:
            self.value = value

        def scalar_one(self) -> object:
            return self.value

        def mappings(self) -> "Result":
            return self

        def all(self) -> object:
            return self.value

    class Session:
        calls = 0

        async def execute(self, _statement: object, _parameters: object = None) -> Result:
            self.calls += 1
            if self.calls == 1:
                return Result(3)
            return Result(
                [
                    {
                        "slug": "test",
                        "name": "Test",
                        "category": "food",
                        "floor": "EG",
                        "address_display_name": None,
                        "occupancy_status": "UNKNOWN",
                        "business_structure": "UNKNOWN",
                        "updated_at": datetime.now(UTC),
                        "district_slug": None,
                        "district_name": None,
                        "quarter_slug": None,
                        "quarter_name": None,
                    }
                ]
            )

    page = await polygon_directory_page(Session(), offset=0, limit=1)  # type: ignore[arg-type]
    assert page.total == 3
    assert page.next_offset == 1
    assert [item.slug for item in page.items] == ["test"]


def request(if_none_match: str | None = None) -> Request:
    headers = [] if if_none_match is None else [(b"if-none-match", if_none_match.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


@pytest.mark.asyncio
async def test_polygon_preview_endpoint_returns_webp_and_honors_etag(monkeypatch) -> None:
    polygon = SimpleNamespace(
        slug="test",
        updated_at=datetime.now(UTC),
        geometry=SimpleNamespace(model_dump=lambda: GEOMETRY),
        bbox=(9.43, 54.78, 9.44, 54.79),
        category="food",
    )
    monkeypatch.setattr(polygon_api, "guard_public_query", AsyncMock())
    monkeypatch.setattr(polygon_api, "public_polygon_by_slug", AsyncMock(return_value=polygon))
    monkeypatch.setattr(
        polygon_api.map_preview_service,
        "get",
        AsyncMock(return_value=MapPreview(b"RIFFxxxxWEBP", '"preview-etag"', False)),
    )

    response = await polygon_api.get_polygon_preview("test", object(), request(), 1200, 630)
    not_modified = await polygon_api.get_polygon_preview(
        "test", object(), request('"preview-etag"'), 1200, 630
    )

    assert response.status_code == 200
    assert response.media_type == "image/webp"
    assert response.body == b"RIFFxxxxWEBP"
    assert response.headers["etag"] == '"preview-etag"'
    assert response.headers["cache-control"] == (
        "public, max-age=86400, stale-while-revalidate=604800"
    )
    assert not_modified.status_code == 304
    assert not_modified.body == b""
    polygon_api.map_preview_service.get.assert_awaited_with(
        slug="test",
        updated_at=polygon.updated_at,
        geometry=GEOMETRY,
        bbox=polygon.bbox,
        width=1200,
        height=630,
        category="food",
        feature_kind="polygon",
    )


@pytest.mark.asyncio
async def test_polygon_preview_endpoint_returns_404_when_public_lookup_rejects_slug(
    monkeypatch,
) -> None:
    monkeypatch.setattr(polygon_api, "guard_public_query", AsyncMock())
    monkeypatch.setattr(polygon_api, "public_polygon_by_slug", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as error:
        await polygon_api.get_polygon_preview("private", object(), request(), 1200, 630)

    assert error.value.status_code == 404
    assert error.value.detail == "Die Fläche wurde nicht gefunden."

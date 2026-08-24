from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.api.analysis_areas as analysis_area_api
import app.api.polygons as polygon_api
from app.schemas.polygon_directory import PolygonDirectoryItem
from app.services.map_previews import MapPreview, MapPreviewRenderer, MapPreviewService
from app.services.polygon_directory import DIRECTORY_SQL, polygon_directory_page

GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[9.43, 54.78], [9.44, 54.78], [9.44, 54.79], [9.43, 54.78]]],
}


class RecordingRenderer(MapPreviewRenderer):
    def __init__(self) -> None:
        self.calls = 0

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
        assert geometry == GEOMETRY
        assert bbox == (9.43, 54.78, 9.44, 54.79)
        assert (width, height) == (640, 360)
        assert category == "food"
        assert feature_kind == "polygon"
        return b"RIFFxxxxWEBP"


@pytest.mark.asyncio
async def test_preview_cache_uses_version_style_and_dimensions(tmp_path) -> None:
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

    assert first.body == b"RIFFxxxxWEBP"
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.etag == first.etag
    assert changed.etag != first.etag
    assert renderer.calls == 2
    assert not list((tmp_path / "cache").rglob("*.partial"))


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

    response = await polygon_api.get_polygon_preview("test", object(), request(), 640, 360)
    not_modified = await polygon_api.get_polygon_preview(
        "test", object(), request('"preview-etag"'), 640, 360
    )

    assert response.status_code == 200
    assert response.media_type == "image/webp"
    assert response.body == b"RIFFxxxxWEBP"
    assert response.headers["etag"] == '"preview-etag"'
    assert not_modified.status_code == 304
    assert not_modified.body == b""


@pytest.mark.asyncio
async def test_area_preview_endpoint_returns_webp_and_unknown_slug_is_404(monkeypatch) -> None:
    area = SimpleNamespace(
        slug="altstadt",
        updated_at=datetime.now(UTC),
        geometry=SimpleNamespace(model_dump=lambda: GEOMETRY),
        bbox=(9.43, 54.78, 9.44, 54.79),
    )
    monkeypatch.setattr(analysis_area_api, "guard_public_query", AsyncMock())
    detail = AsyncMock(return_value=area)
    monkeypatch.setattr(analysis_area_api, "area_detail_by_slug", detail)
    monkeypatch.setattr(
        analysis_area_api.map_preview_service,
        "get",
        AsyncMock(return_value=MapPreview(b"RIFFxxxxWEBP", '"area-etag"', False)),
    )

    response = await analysis_area_api.get_area_preview(
        "altstadt", object(), request(), 640, 360
    )
    assert response.status_code == 200
    assert response.media_type == "image/webp"

    detail.return_value = None
    with pytest.raises(HTTPException) as error:
        await analysis_area_api.get_area_preview("missing", object(), request(), 640, 360)
    assert error.value.status_code == 404

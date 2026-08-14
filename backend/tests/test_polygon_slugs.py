from unittest.mock import AsyncMock

import pytest

import app.services.polygons as polygon_service
from app.models.user_polygon import UserPolygon
from app.schemas.geojson import PolygonUpdate
from app.services.polygons import generate_unique_polygon_slug, slugify_polygon_name, update_polygon


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Große Straße 42", "grosse-strasse-42"),
        ("Fläche am Holm", "flaeche-am-holm"),
        ("Café & Bar", "cafe-bar"),
        ("  Viele --- Abstände  ", "viele-abstaende"),
        ("!!!", "flaeche"),
    ],
)
def test_slugify_polygon_name(name: str, expected: str) -> None:
    assert slugify_polygon_name(name) == expected


def test_slugify_polygon_name_leaves_room_for_unique_suffix() -> None:
    assert len(slugify_polygon_name("ä" * 160)) == 240


@pytest.mark.asyncio
async def test_generate_unique_polygon_slug_adds_next_available_suffix() -> None:
    session = FakeSlugSession(
        {"holmpassage-flensburg", "holmpassage-flensburg-2", "holmpassage-flensburg-4"}
    )

    slug = await generate_unique_polygon_slug(session, "Holmpassage Flensburg")  # type: ignore[arg-type]

    assert slug == "holmpassage-flensburg-3"


class FakeSlugSession:
    def __init__(self, slugs: set[str]) -> None:
        self.slugs = slugs

    async def scalars(self, _statement: object) -> set[str]:
        return self.slugs


@pytest.mark.asyncio
async def test_polygon_slug_stays_stable_when_name_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    polygon = UserPolygon(name="Alter Name", slug="stabile-url", category="custom")
    session = FakeUpdateSession()
    monkeypatch.setattr(polygon_service, "serialize_polygon", lambda item: item.slug)
    monkeypatch.setattr(polygon_service, "bump_cache_versions", AsyncMock(return_value=None))

    result = await update_polygon(
        session,  # type: ignore[arg-type]
        polygon,
        PolygonUpdate(name="Völlig neuer Name"),
    )

    assert result == "stabile-url"
    assert polygon.name == "Völlig neuer Name"
    assert polygon.slug == "stabile-url"


class FakeUpdateSession:
    async def commit(self) -> None:
        pass

    async def refresh(self, _item: object) -> None:
        pass

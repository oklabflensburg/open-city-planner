import uuid
from unittest.mock import AsyncMock

import pytest

import app.services.polygons as polygon_service
from app.models.user_polygon import UserPolygon
from app.schemas.geojson import PolygonUpdate
from app.services.polygons import (
    delete_polygon,
    generate_unique_polygon_slug,
    slugify_polygon_name,
    update_polygon,
)


@pytest.fixture(autouse=True)
def disable_notification_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(polygon_service, "subscription_recipient_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(polygon_service, "notify_users", AsyncMock(return_value=[]))
    monkeypatch.setattr(polygon_service, "publish_notifications", lambda _items: None)


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
    monkeypatch.setattr(polygon_service, "invalidate_gis_after_mutation", AsyncMock(return_value=None))

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

    async def flush(self) -> None:
        pass

    async def refresh(self, _item: object) -> None:
        pass


@pytest.mark.asyncio
async def test_delete_invalidates_polygon_analytics_and_osm_namespaces(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeDeleteSession()
    polygon = UserPolygon(name="Delete me", slug="delete-me", category="custom")
    polygon.uuid = uuid.uuid4()
    bump = AsyncMock(return_value=None)
    cancel_publications = AsyncMock(return_value=0)
    monkeypatch.setattr(polygon_service, "invalidate_gis_after_mutation", bump)
    monkeypatch.setattr(
        "app.services.social_publishing.cancel_pending_polygon_publications",
        cancel_publications,
    )

    await delete_polygon(session, polygon, uuid.uuid4())  # type: ignore[arg-type]

    bump.assert_awaited_once_with(session)
    cancel_publications.assert_awaited_once_with(session, polygon.uuid)
    assert session.deleted is polygon
    assert session.committed is True
    assert session.added[0].action == "POLYGON_DELETED"
    assert session.added[0].event_metadata == {"title": "Delete me"}


class FakeDeleteSession:
    deleted: object | None = None
    committed = False

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        pass

    async def delete(self, item: object) -> None:
        self.deleted = item

    async def commit(self) -> None:
        self.committed = True

import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Self

import httpx
import pytest
from pydantic import ValidationError

import app.api.polygons as polygons_api
from app.auth.dependencies import (
    can_create_polygon,
    can_delete_polygon,
    can_edit_polygon,
    has_role,
)
from app.auth.jwt import create_jwt
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.schemas.geojson import (
    PolygonRead,
    PolygonUpdate,
    PolygonVerwaltungUpdate,
    PublicPolygonDetail,
)
from app.services import nominatim, polygons
from app.services.nominatim import NominatimAddress, NominatimService
from app.services.polygons import polygon_slug_source, slugify_polygon_name

TEST_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[9.4364, 54.7848], [9.4372, 54.7851], [9.4374, 54.7846], [9.4364, 54.7848]]],
}


def test_verwaltung_role_is_central_and_case_robust() -> None:
    user = SimpleNamespace(is_superuser=False, roles=["USER", "verwaltung"])
    assert has_role(user, "VERWALTUNG") is True
    assert has_role(SimpleNamespace(is_superuser=False, roles=["USER"]), "VERWALTUNG") is False
    assert has_role(SimpleNamespace(is_superuser=True, roles=[]), "VERWALTUNG") is True


def test_polygon_permissions_separate_create_edit_and_delete() -> None:
    owner_id = uuid.uuid4()
    owner = SimpleNamespace(
        id=owner_id,
        is_active=True,
        is_superuser=False,
        roles=["USER"],
    )
    stranger = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        roles=["USER"],
    )
    verwaltung = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        roles=["VERWALTUNG"],
    )

    assert can_create_polygon(owner) is True
    assert can_edit_polygon(owner, owner_id) is True
    assert can_delete_polygon(owner, owner_id) is True
    assert can_edit_polygon(stranger, owner_id) is False
    assert can_delete_polygon(stranger, owner_id) is False
    assert can_edit_polygon(verwaltung, owner_id) is True
    assert can_delete_polygon(verwaltung, owner_id) is True


def test_public_polygon_schema_has_no_management_fields() -> None:
    public_fields = set(PublicPolygonDetail.model_fields)
    assert not public_fields.intersection(
        {"owner_name", "owner_street", "owner_city", "price_per_sqm", "updated_by_user_id"}
    )


def test_management_price_uses_decimal_and_rejects_negative_values() -> None:
    payload = PolygonVerwaltungUpdate(price_per_sqm="24.50")
    assert payload.price_per_sqm == Decimal("24.50")
    with pytest.raises(ValidationError):
        PolygonVerwaltungUpdate(price_per_sqm="-0.01")


def test_management_field_is_detectable_on_public_patch() -> None:
    payload = PolygonUpdate(price_per_sqm="24.50")
    assert payload.model_extra == {"price_per_sqm": "24.50"}


def test_area_size_is_a_supported_public_polygon_property() -> None:
    payload = PolygonUpdate(area_size="XL")
    assert payload.area_size == "XL"
    assert payload.model_extra == {}


def test_slug_uses_floor_and_structured_address() -> None:
    polygon = SimpleNamespace(
        floor="EG",
        address_street="Große Straße",
        address_house_number="42",
        address_city="Flensburg",
        uuid="a83f2100-0000-0000-0000-000000000000",
    )
    assert slugify_polygon_name(polygon_slug_source(polygon)) == "eg-grosse-strasse-42-flensburg"


def test_nominatim_address_keeps_missing_house_number_optional() -> None:
    address = NominatimAddress(
        display_name="Holm, Flensburg",
        street="Holm",
        house_number=None,
        postal_code="24937",
        city="Flensburg",
        country="Deutschland",
    )
    assert address.house_number is None
    assert address.city == "Flensburg"


@pytest.mark.asyncio
async def test_nominatim_reverse_normalizes_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["user-agent"] == "OpenCityMap tests"
        return httpx.Response(
            200,
            json={
                "display_name": "Holm, 24937 Flensburg, Deutschland",
                "address": {"road": "Holm", "postcode": "24937", "city": "Flensburg", "country": "Deutschland"},
            },
        )

    transport = httpx.MockTransport(handler)

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr(nominatim, "get_settings", lambda: SimpleNamespace(
        nominatim_base_url="https://nominatim.test",
        nominatim_email=None,
        nominatim_user_agent="OpenCityMap tests",
        nominatim_timeout_seconds=1,
        nominatim_cache_ttl_seconds=60,
    ))
    monkeypatch.setattr(nominatim.httpx, "AsyncClient", Client)
    nominatim._cache.clear()

    first = await NominatimService().reverse(54.783001, 9.435001)
    second = await NominatimService().reverse(54.783002, 9.435002)

    assert first == second
    assert first and first.street == "Holm" and first.house_number is None
    assert calls == 1


@pytest.mark.asyncio
async def test_nominatim_timeout_is_reported_to_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    class TimeoutClient:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *_args: object, **_kwargs: object) -> None:
            raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(nominatim, "get_settings", lambda: SimpleNamespace(
        nominatim_base_url="https://nominatim.test",
        nominatim_email=None,
        nominatim_user_agent="OpenCityMap tests",
        nominatim_timeout_seconds=1,
        nominatim_cache_ttl_seconds=60,
    ))
    monkeypatch.setattr(nominatim.httpx, "AsyncClient", lambda **_kwargs: TimeoutClient())

    with pytest.raises(httpx.ReadTimeout):
        await NominatimService().reverse(50.0, 10.0)


@pytest.mark.asyncio
async def test_address_enrichment_failure_does_not_fail_saved_polygon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    polygon = SimpleNamespace(uuid="a83f2100", address_lookup_status="pending")

    class Session:
        rollback_count = 0
        commit_count = 0

        async def rollback(self) -> None:
            self.rollback_count += 1

        async def commit(self) -> None:
            self.commit_count += 1

        async def refresh(self, _polygon: object) -> None:
            return None

    async def point(*_args: object) -> tuple[float, float]:
        return 54.78, 9.43

    async def timeout(*_args: object) -> None:
        raise httpx.ReadTimeout("timeout")

    async def get_polygon(*_args: object, **_kwargs: object) -> object:
        return polygon

    monkeypatch.setattr(polygons, "polygon_point_on_surface", point)
    monkeypatch.setattr(polygons.NominatimService, "reverse", timeout)
    monkeypatch.setattr(polygons, "get_polygon", get_polygon)
    session = Session()

    assert await polygons.enrich_polygon_address(session, polygon) is False
    assert polygon.address_lookup_status == "failed"
    assert session.rollback_count == 1
    assert session.commit_count == 1


class PolygonApiSession:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def get(self, _model: object, _key: object) -> User | None:
        return self.user


def polygon_read(owner_id: uuid.UUID) -> PolygonRead:
    return PolygonRead(
        id=str(uuid.uuid4()),
        slug="meine-verkaufsflaeche-10",
        name="Meine Verkaufsfläche",
        description="",
        floor="EG",
        category="services",
        geometry=TEST_GEOMETRY,
        properties={"size": "L"},
        created_by_user_id=str(owner_id),
        updated_by_user_id=str(owner_id),
        created_at="2026-08-10T11:35:14Z",
        updated_at="2026-08-13T08:00:00Z",
    )


def public_polygon_detail() -> PublicPolygonDetail:
    return PublicPolygonDetail(
        id=str(uuid.uuid4()),
        slug="meine-verkaufsflaeche-10",
        name="Meine Verkaufsfläche",
        description="",
        floor="EG",
        area_size="L",
        address_display_name=None,
        address_street=None,
        address_house_number=None,
        address_postal_code=None,
        address_city=None,
        address_country=None,
        address_lookup_status="pending",
        category="services",
        geometry=TEST_GEOMETRY,
        area_m2=3291.84,
        perimeter_m=236.87,
        centroid=(9.4369, 54.7847),
        bbox=(9.4364, 54.7846, 9.4374, 54.7851),
        created_at="2026-08-10T11:35:14Z",
        updated_at="2026-08-13T08:00:00Z",
    )


@pytest.mark.asyncio
async def test_public_lookup_loads_concrete_polygon_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_slugs: list[str] = []

    async def override_session():
        yield PolygonApiSession()

    async def fake_by_slug(_session: object, slug: str) -> PublicPolygonDetail:
        requested_slugs.append(slug)
        return public_polygon_detail()

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(polygons_api, "public_polygon_by_slug", fake_by_slug)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/polygons/by-slug/meine-verkaufsflaeche-10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert requested_slugs == ["meine-verkaufsflaeche-10"]
    assert response.json()["geometry"] == TEST_GEOMETRY


async def patch_geometry_as(
    user: User | None,
    owner_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> httpx.Response:
    session = PolygonApiSession(user)

    async def override_session():
        yield session

    async def fake_get_polygon(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(created_by_user_id=owner_id)

    async def fake_update_polygon(*_args: object, **_kwargs: object) -> PolygonRead:
        return polygon_read(owner_id)

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(polygons_api, "get_polygon", fake_get_polygon)
    monkeypatch.setattr(polygons_api, "update_polygon", fake_update_polygon)
    cookies = {"ocm_csrf_token": "csrf-token"}
    headers = {"x-csrf-token": "csrf-token"}
    if user:
        access_token, _ = create_jwt(
            str(user.id),
            "access",
            timedelta(minutes=5),
            {"email": user.email, "role": "user"},
        )
        cookies["ocm_access_token"] = access_token
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
        ) as client:
            return await client.patch(
                f"/api/v1/polygons/{uuid.uuid4()}",
                json={"geometry": TEST_GEOMETRY},
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_anonymous_user_cannot_patch_polygon_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    response = await patch_geometry_as(None, uuid.uuid4(), monkeypatch)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_owner_cannot_patch_polygon_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.org",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        roles=["USER"],
    )
    response = await patch_geometry_as(user, uuid.uuid4(), monkeypatch)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_patch_polygon_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    owner_id = uuid.uuid4()
    user = User(
        id=owner_id,
        email="owner@example.org",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        roles=["USER"],
    )
    response = await patch_geometry_as(user, owner_id, monkeypatch)
    assert response.status_code == 200
    assert response.json()["slug"] == "meine-verkaufsflaeche-10"
    assert response.json()["geometry"] == TEST_GEOMETRY


def active_user(*, roles: list[str] | None = None, verified: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4()}@example.org",
        is_active=True,
        is_verified=verified,
        is_superuser=False,
        roles=roles or ["USER"],
    )


def auth_request_parts(user: User | None) -> tuple[dict[str, str], dict[str, str]]:
    cookies = {"ocm_csrf_token": "csrf-token"}
    headers = {"x-csrf-token": "csrf-token"}
    if user is not None:
        access_token, _ = create_jwt(
            str(user.id),
            "access",
            timedelta(minutes=5),
            {"email": user.email, "role": "user"},
        )
        cookies["ocm_access_token"] = access_token
    return cookies, headers


async def create_polygon_as(
    user: User | None,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[httpx.Response, list[tuple[object, uuid.UUID]]]:
    captured: list[tuple[object, uuid.UUID]] = []

    async def override_session():
        yield PolygonApiSession(user)

    async def fake_create(_session: object, payload: object, user_id: uuid.UUID) -> PolygonRead:
        captured.append((payload, user_id))
        return polygon_read(user_id)

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(polygons_api, "create_polygon", fake_create)
    cookies, headers = auth_request_parts(user)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
        ) as client:
            response = await client.post(
                "/api/v1/polygons",
                json={
                    "name": "Neue Fläche",
                    "floor": "EG",
                    "category": "services",
                    "geometry": TEST_GEOMETRY,
                    "properties": {},
                },
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()
    return response, captured


@pytest.mark.asyncio
async def test_anonymous_user_cannot_create_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    response, captured = await create_polygon_as(None, monkeypatch)
    assert response.status_code == 401
    assert captured == []


@pytest.mark.asyncio
@pytest.mark.parametrize("roles", [["USER"], ["VERWALTUNG"]])
async def test_active_user_can_create_polygon_with_server_ownership(
    roles: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = active_user(roles=roles, verified=False)
    response, captured = await create_polygon_as(user, monkeypatch)

    assert response.status_code == 201
    assert response.json()["slug"] == "meine-verkaufsflaeche-10"
    assert response.json()["geometry"] == TEST_GEOMETRY
    assert len(captured) == 1
    payload, owner_id = captured[0]
    assert owner_id == user.id
    assert payload.geometry.model_dump(mode="json") == TEST_GEOMETRY


async def delete_polygon_as(
    user: User | None,
    owner_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[httpx.Response, list[tuple[uuid.UUID, uuid.UUID]]]:
    deleted: list[tuple[uuid.UUID, uuid.UUID]] = []
    polygon_id = uuid.uuid4()

    async def override_session():
        yield PolygonApiSession(user)

    async def fake_get_polygon(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(uuid=polygon_id, created_by_user_id=owner_id)

    async def fake_delete(_session: object, polygon: object, actor_id: uuid.UUID) -> None:
        deleted.append((polygon.uuid, actor_id))

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(polygons_api, "get_polygon", fake_get_polygon)
    monkeypatch.setattr(polygons_api, "delete_polygon", fake_delete)
    cookies, headers = auth_request_parts(user)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
        ) as client:
            response = await client.delete(
                f"/api/v1/polygons/{polygon_id}",
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()
    return response, deleted


@pytest.mark.asyncio
async def test_anonymous_user_cannot_delete_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    response, deleted = await delete_polygon_as(None, uuid.uuid4(), monkeypatch)
    assert response.status_code == 401
    assert deleted == []


@pytest.mark.asyncio
async def test_owner_can_delete_own_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = active_user(verified=False)
    response, deleted = await delete_polygon_as(owner, owner.id, monkeypatch)
    assert response.status_code == 204
    assert deleted and deleted[0][1] == owner.id


@pytest.mark.asyncio
async def test_non_owner_cannot_delete_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    stranger = active_user(verified=True)
    response, deleted = await delete_polygon_as(stranger, uuid.uuid4(), monkeypatch)
    assert response.status_code == 403
    assert deleted == []


@pytest.mark.asyncio
async def test_verwaltung_can_delete_any_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    verwaltung = active_user(roles=["VERWALTUNG"], verified=False)
    response, deleted = await delete_polygon_as(verwaltung, uuid.uuid4(), monkeypatch)
    assert response.status_code == 204
    assert deleted and deleted[0][1] == verwaltung.id


@pytest.mark.asyncio
async def test_deleted_polygon_slug_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = active_user(verified=False)
    polygon_id = uuid.uuid4()
    exists = True

    async def override_session():
        yield PolygonApiSession(owner)

    async def fake_get_polygon(*_args: object, **_kwargs: object) -> object | None:
        if not exists:
            return None
        return SimpleNamespace(uuid=polygon_id, created_by_user_id=owner.id)

    async def fake_delete(_session: object, _polygon: object, _actor_id: uuid.UUID) -> None:
        nonlocal exists
        exists = False

    async def fake_by_slug(_session: object, _slug: str) -> PublicPolygonDetail | None:
        return public_polygon_detail() if exists else None

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(polygons_api, "get_polygon", fake_get_polygon)
    monkeypatch.setattr(polygons_api, "delete_polygon", fake_delete)
    monkeypatch.setattr(polygons_api, "public_polygon_by_slug", fake_by_slug)
    cookies, headers = auth_request_parts(owner)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies=cookies,
        ) as client:
            delete_response = await client.delete(
                f"/api/v1/polygons/{polygon_id}",
                headers=headers,
            )
            get_response = await client.get(
                "/api/v1/polygons/by-slug/meine-verkaufsflaeche-10"
            )
    finally:
        app.dependency_overrides.clear()

    assert delete_response.status_code == 204
    assert get_response.status_code == 404

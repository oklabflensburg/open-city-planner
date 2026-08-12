from decimal import Decimal
from types import SimpleNamespace
from typing import Self

import httpx
import pytest
from pydantic import ValidationError

from app.auth.dependencies import has_role
from app.schemas.geojson import PolygonUpdate, PolygonVerwaltungUpdate, PublicPolygonDetail
from app.services import nominatim, polygons
from app.services.nominatim import NominatimAddress, NominatimService
from app.services.polygons import polygon_slug_source, slugify_polygon_name


def test_verwaltung_role_is_central_and_case_robust() -> None:
    user = SimpleNamespace(is_superuser=False, roles=["USER", "verwaltung"])
    assert has_role(user, "VERWALTUNG") is True
    assert has_role(SimpleNamespace(is_superuser=False, roles=["USER"]), "VERWALTUNG") is False
    assert has_role(SimpleNamespace(is_superuser=True, roles=[]), "VERWALTUNG") is True


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

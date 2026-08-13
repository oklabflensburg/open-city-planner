import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

import app.api.analytics as analytics_api
from app.auth.jwt import create_jwt
from app.db.session import get_session
from app.main import app
from app.models.city_metrics import CityMetrics
from app.models.user import User
from app.schemas.analytics import (
    CityMetricsUpdate,
    CityMetricsVerwaltungRead,
)
from app.services.city_metrics import update_city_metrics


class FakeSession:
    def __init__(self, record: CityMetrics | None = None, user: User | None = None) -> None:
        self.record = record
        self.user = user
        self.added: list[object] = []

    async def scalar(self, _statement: object) -> CityMetrics | None:
        return self.record

    async def get(self, _model: object, _key: object) -> User | None:
        return self.user

    def add(self, item: object) -> None:
        self.added.append(item)
        if isinstance(item, CityMetrics):
            self.record = item

    async def commit(self) -> None:
        pass

    async def refresh(self, item: object) -> None:
        if isinstance(item, CityMetrics):
            item.id = item.id or uuid.uuid4()
            item.created_at = getattr(item, "created_at", None) or datetime.now(UTC)


def metric_record() -> CityMetrics:
    return CityMetrics(
        id=uuid.uuid4(),
        vacancy_rate=Decimal("6.25"),
        chain_store_rate=Decimal("71.00"),
        centrality_index=Decimal("154.00"),
        purchasing_power_index=Decimal("85.00"),
        reference_date=date(2026, 6, 30),
        source="Echte Quelle",
        notes="Interner Hinweis",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vacancy_rate", "-0.01"),
        ("vacancy_rate", "100.01"),
        ("chain_store_rate", "-0.01"),
        ("chain_store_rate", "100.01"),
        ("centrality_index", "-0.01"),
        ("purchasing_power_index", "-0.01"),
    ],
)
def test_city_metric_validation_rejects_implausible_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        CityMetricsUpdate(**{field: value})


def test_city_metrics_allow_null_without_fake_defaults() -> None:
    payload = CityMetricsUpdate(vacancy_rate=None)
    assert payload.vacancy_rate is None
    assert payload.model_dump(exclude_unset=True) == {"vacancy_rate": None}


@pytest.mark.asyncio
async def test_partial_update_preserves_other_values_and_sets_updated_by() -> None:
    record = metric_record()
    original_chain_rate = record.chain_store_rate
    user_id = uuid.uuid4()
    session = FakeSession(record)

    result = await update_city_metrics(
        session,  # type: ignore[arg-type]
        CityMetricsUpdate(vacancy_rate="7.50"),
        user_id,
    )

    assert result.vacancy_rate == Decimal("7.50")
    assert record.chain_store_rate == original_chain_rate
    assert record.updated_by_user_id == user_id


@pytest.mark.asyncio
async def test_metric_can_be_cleared_explicitly() -> None:
    record = metric_record()
    session = FakeSession(record)

    result = await update_city_metrics(
        session,  # type: ignore[arg-type]
        CityMetricsUpdate(centrality_index=None),
        uuid.uuid4(),
    )

    assert result.centrality_index is None
    assert record.centrality_index is None


async def request_with_user(user: User | None, monkeypatch: pytest.MonkeyPatch) -> httpx.Response:
    session = FakeSession(user=user)

    async def override_session():
        yield session

    async def fake_update(*_args: object, **_kwargs: object) -> CityMetricsVerwaltungRead:
        return CityMetricsVerwaltungRead(vacancy_rate=Decimal("7.50"))

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(analytics_api, "update_city_metrics", fake_update)
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
                "/api/v1/analytics/fast-facts",
                json={"vacancy_rate": 7.5},
                headers=headers,
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_anonymous_user_cannot_patch_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    response = await request_with_user(None, monkeypatch)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_normal_user_cannot_patch_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="user@example.org",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        roles=["USER"],
    )
    response = await request_with_user(user, monkeypatch)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_verwaltung_can_patch_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id=uuid.uuid4(),
        email="verwaltung@example.org",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        roles=["VERWALTUNG"],
    )
    response = await request_with_user(user, monkeypatch)
    assert response.status_code == 200
    assert response.json()["vacancy_rate"] == 7.5

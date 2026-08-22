import httpx
import pytest

from app import main as main_module


@pytest.mark.asyncio
async def test_health_live_is_liveness_only() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app),
        base_url="https://api.stadtplaner.oklabflensburg.de",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_reports_database_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_database_health() -> str:
        return "down"

    async def fake_redis_health() -> str:
        return "disabled"

    monkeypatch.setattr(main_module, "database_health", fake_database_health)
    monkeypatch.setattr(main_module, "redis_health", fake_redis_health)
    monkeypatch.setattr(main_module.settings, "redis_enabled", False, raising=False)
    monkeypatch.setattr(main_module.settings, "redis_required", False, raising=False)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app),
        base_url="https://api.stadtplaner.oklabflensburg.de",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] == "down"
    assert response.json()["redis"] == "disabled"


@pytest.mark.asyncio
async def test_health_ready_uses_required_redis_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_database_health() -> str:
        return "ok"

    async def fake_redis_health() -> str:
        return "degraded"

    monkeypatch.setattr(main_module, "database_health", fake_database_health)
    monkeypatch.setattr(main_module, "redis_health", fake_redis_health)
    monkeypatch.setattr(main_module.settings, "redis_enabled", True, raising=False)
    monkeypatch.setattr(main_module.settings, "redis_required", True, raising=False)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app),
        base_url="https://api.stadtplaner.oklabflensburg.de",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] == "ok"
    assert response.json()["redis"] == "degraded"


@pytest.mark.asyncio
async def test_health_ready_allows_optional_redis_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_database_health() -> str:
        return "ok"

    async def fake_redis_health() -> str:
        return "degraded"

    monkeypatch.setattr(main_module, "database_health", fake_database_health)
    monkeypatch.setattr(main_module, "redis_health", fake_redis_health)
    monkeypatch.setattr(main_module.settings, "redis_enabled", True, raising=False)
    monkeypatch.setattr(main_module.settings, "redis_required", False, raising=False)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main_module.app),
        base_url="https://api.stadtplaner.oklabflensburg.de",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "degraded"}

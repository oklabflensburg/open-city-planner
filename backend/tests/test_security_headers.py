import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/docs", "/redoc"])
async def test_api_documentation_csp_allows_loading_openapi_schema(path: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://api.stadtplaner.oklabflensburg.de",
    ) as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert "connect-src 'self'" in response.headers["content-security-policy"]

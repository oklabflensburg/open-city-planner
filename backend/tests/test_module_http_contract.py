import ast
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.integrations import module_host_ports
from app.integrations.module_host_ports import HostModuleHttpClientFactory
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.runtime import create_module_runtime
from tests.fixtures.http_contract_module import (
    DEFINITION,
    fetch_provider_document,
)
from tests.test_module_runtime import FakeDiscovery

ROOT = Path(__file__).resolve().parents[2]


class TrackingTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        handler: Callable[[httpx.Request], Awaitable[httpx.Response]],
    ) -> None:
        self._handler = handler
        self.requests: list[httpx.Request] = []
        self.closed = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self._handler(request)

    async def aclose(self) -> None:
        self.closed = True


def _runtime_with_http(adapter: HostModuleHttpClientFactory):
    return create_module_runtime(
        enabled_module_ids=(DEFINITION.declared_id,),
        discovery_providers=(FakeDiscovery((DEFINITION,)),),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(ModuleHostServices(http=adapter)),
    )


@pytest.mark.asyncio
async def test_external_module_uses_production_http_port_without_network() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"entity": "Q481"}, request=request)

    transport = TrackingTransport(handler)
    settings = Settings(_env_file=None, api_version="9.8.7")
    adapter = HostModuleHttpClientFactory(settings=settings, transport=transport)
    runtime = _runtime_with_http(adapter)
    context = runtime.registry.get(DEFINITION.declared_id).context

    assert context.http is adapter
    response = await fetch_provider_document(context)

    assert response.status_code == 200
    assert response.json() == {"entity": "Q481"}
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert str(request.url) == "https://provider.example/document?format=json"
    assert request.headers["user-agent"] == (
        "Stadtplaner/9.8.7 (module-http; https://stadtplaner.oklabflensburg.de)"
    )
    assert "Stadtplaner/1.0" not in request.headers["user-agent"]
    assert "authorization" not in request.headers
    assert "cookie" not in request.headers
    assert "x-internal-token" not in request.headers
    assert request.extensions["timeout"] == {
        "connect": 10.0,
        "read": 10.0,
        "write": 10.0,
        "pool": 10.0,
    }
    assert transport.closed is True


@pytest.mark.asyncio
async def test_transport_error_is_not_retried_and_client_is_closed() -> None:
    timeout: httpx.ReadTimeout | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout
        timeout = httpx.ReadTimeout("controlled timeout", request=request)
        raise timeout

    transport = TrackingTransport(handler)
    context = _runtime_with_http(
        HostModuleHttpClientFactory(transport=transport)
    ).registry.get(DEFINITION.declared_id).context

    with pytest.raises(httpx.ReadTimeout) as caught:
        await fetch_provider_document(context)

    assert caught.value is timeout
    assert len(transport.requests) == 1
    assert transport.closed is True


@pytest.mark.asyncio
async def test_http_observability_uses_service_and_method_not_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, str] = {}

    async def observe(
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        provider: str,
        operation: str,
        **kwargs: object,
    ) -> httpx.Response:
        observed.update(provider=provider, operation=operation, requested_url=url)
        return await client.request(method, url, **kwargs)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, request=request)

    monkeypatch.setattr(module_host_ports, "instrumented_httpx_request", observe)
    context = _runtime_with_http(
        HostModuleHttpClientFactory(transport=TrackingTransport(handler))
    ).registry.get(DEFINITION.declared_id).context

    await fetch_provider_document(context)

    assert observed == {
        "provider": "wikidata",
        "operation": "GET",
        "requested_url": "/document",
    }
    assert "provider.example" not in observed["provider"]
    assert "/document" not in observed["operation"]


def test_production_compositions_wire_http_factory() -> None:
    from app import main
    from app.cli import process_domain_event_outbox

    assert main.module_runtime.registry.records
    assert all(
        isinstance(record.context.http, HostModuleHttpClientFactory)
        for record in main.module_runtime.registry.records
    )
    worker_source = inspect.getsource(process_domain_event_outbox.run)
    assert "http=HostModuleHttpClientFactory(settings=settings)" in worker_source


def test_external_fixture_imports_only_public_sdk() -> None:
    source = ROOT / "backend/tests/fixtures/http_contract_module.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    host_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
    }

    assert host_imports == {"app.platform.modules.sdk"}


def test_http_adapter_is_generic_and_reuses_existing_contract() -> None:
    source = inspect.getsource(module_host_ports).lower()

    assert "analysis-areas" not in source
    assert "analysis_areas" not in source
    assert "modulehttpport" not in source
    assert "externalhttpclientservice" not in source
    assert "trustedhttpfactory" not in source


@pytest.mark.parametrize(
    ("service_name", "base_url"),
    (
        ("Wikidata", "https://provider.example"),
        ("wikidata/user", "https://provider.example"),
        ("wikidata", "https://user:secret@provider.example"),
    ),
)
@pytest.mark.asyncio
async def test_factory_rejects_unstable_service_names_and_url_credentials(
    service_name: str,
    base_url: str,
) -> None:
    factory = HostModuleHttpClientFactory()

    with pytest.raises(ValueError):
        async with factory.create(service_name=service_name, base_url=base_url):
            pytest.fail("invalid clients must not be created")


@pytest.mark.asyncio
async def test_client_rejects_nonstandard_metric_method() -> None:
    factory = HostModuleHttpClientFactory(transport=httpx.MockTransport(lambda request: None))

    async with factory.create(
        service_name="wikidata",
        base_url="https://provider.example",
    ) as client:
        with pytest.raises(ValueError, match="standard method"):
            await client.request("GET-Q481", "/document")

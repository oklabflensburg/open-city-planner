import json
import logging
from io import StringIO

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import AsyncOpenTelemetryTransport
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import generate_latest
from starlette.requests import Request

from app import main as main_module
from app.cache.service import CacheService
from app.observability.external import instrumented_httpx_request
from app.observability.logging import JsonFormatter
from app.observability.metrics import (
    EXTERNAL_ERRORS,
    EXTERNAL_REQUESTS,
    REDIS_ERRORS,
    REDIS_HITS,
    REDIS_MISSES,
    REGISTRY,
)
from app.observability.middleware import ObservabilityMiddleware, request_id_for, route_template
from app.observability.redaction import REDACTED, redact


def test_recursive_redaction_removes_secrets_and_pii() -> None:
    source = {
        "password": "secret",
        "Authorization": "Bearer abc",
        "nested": [{"email": "person@example.org", "totp_secret": "otp-value"}],
        "message": "contact person@example.org using Bearer xyz",
    }

    rendered = json.dumps(redact(source))

    for secret in ("Bearer abc", "person@example.org", "otp-value", "Bearer xyz"):
        assert secret not in rendered
    assert redact(source)["password"] == REDACTED
    assert REDACTED in rendered


def test_json_formatter_redacts_security_and_assistant_fields() -> None:
    formatter = JsonFormatter(service="test", environment="test", release_sha="abc123")
    record = logging.makeLogRecord(
        {
            "name": "privacy",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "request for person@example.org with Bearer abc",
            "args": (),
            "authorization": "Bearer jwt-value",
            "cookie": "session=value",
            "csrf_token": "csrf-value",
            "password": "password-value",
            "recovery_code": "recovery-value",
            "totp_secret": "totp-value",
            "assistant_prompt": "raw private prompt",
            "smtp_password": "smtp-value",
            "api_key": "key-value",
        }
    )

    output = formatter.format(record)

    for value in (
        "person@example.org",
        "Bearer abc",
        "jwt-value",
        "session=value",
        "csrf-value",
        "password-value",
        "recovery-value",
        "totp-value",
        "raw private prompt",
        "smtp-value",
        "key-value",
    ):
        assert value not in output
    assert json.loads(output)["release_sha"] == "abc123"


@pytest.mark.parametrize(
    ("incoming", "accepted"),
    ((None, False), ("edge-123", True), ("bad value\n", False), ("x" * 97, False)),
)
def test_request_id_validation(incoming: str | None, accepted: bool) -> None:
    generated = request_id_for(incoming)
    assert (generated == incoming) is accepted
    assert len(generated) <= 96


def test_dynamic_paths_share_the_fastapi_route_template() -> None:
    def request(path: str) -> Request:
        return Request(
            {
                "type": "http",
                "app": main_module.app,
                "method": "GET",
                "path": path,
                "root_path": "",
                "scheme": "https",
                "query_string": b"",
                "headers": [],
                "server": ("api.example", 443),
                "client": ("127.0.0.1", 1234),
            }
        )

    first = route_template(request("/api/v1/polygons/by-slug/foo"))
    second = route_template(request("/api/v1/polygons/by-slug/bar"))
    assert first == second == "/api/v1/polygons/by-slug/{slug}"


@pytest.mark.asyncio
async def test_request_id_response_log_metrics_and_route_cardinality() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service="test", environment="test", release_sha="sha"))
    middleware_logger = logging.getLogger("app.observability.middleware")
    middleware_logger.addHandler(handler)
    middleware_logger.propagate = False
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main_module.app), base_url="https://api.example"
        ) as client:
            first = await client.get("/health/live", headers={"X-Request-ID": "edge-123"})
            second = await client.get("/health/live", headers={"X-Request-ID": "bad value"})
            metrics = await client.get(main_module.settings.metrics_path)
    finally:
        middleware_logger.removeHandler(handler)
        middleware_logger.propagate = True

    assert first.headers["X-Request-ID"] == "edge-123"
    assert second.headers["X-Request-ID"] != "bad value"
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    first_log = next(item for item in records if item.get("request_id") == "edge-123")
    assert first_log["event"] == "http_request_completed"
    assert first_log["route"] == "/health/live"
    assert first_log["status_code"] == 200
    body = metrics.text
    assert 'http_requests_total{method="GET",route="/health/live",status_class="2xx"}' in body
    assert "http_request_duration_seconds_bucket" in body
    assert "edge-123" not in body


@pytest.mark.asyncio
async def test_fastapi_trace_contains_child_span_and_trace_id_in_log() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware, metrics_enabled=False, metrics_path="/metrics")
    @app.get("/trace")
    async def traced() -> dict[str, bool]:
        async with httpx.AsyncClient(
            transport=AsyncOpenTelemetryTransport(
                httpx.MockTransport(lambda _request: httpx.Response(200)),
                tracer_provider=provider,
            )
        ) as provider_client:
            response = await provider_client.get("https://provider.test/resource")
        return {"ok": response.is_success}

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service="test", environment="test", release_sha="sha"))
    middleware_logger = logging.getLogger("app.observability.middleware")
    middleware_logger.addHandler(handler)
    middleware_logger.propagate = False
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://api.example"
        ) as client:
            assert (await client.get("/trace")).status_code == 200
    finally:
        middleware_logger.removeHandler(handler)
        middleware_logger.propagate = True
        FastAPIInstrumentor.uninstrument_app(app)
        provider.shutdown()

    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert "GET" in names
    assert any("/trace" in name for name in names)
    request_log = json.loads(stream.getvalue().splitlines()[-1])
    assert request_log["trace_id"] == f"{spans[0].context.trace_id:032x}"


class FakeRedis:
    async def get(self, key: str) -> bytes | None:
        if key == "error":
            raise ConnectionError(key)
        return b"value" if key == "hit" else None


@pytest.mark.asyncio
async def test_redis_hit_miss_and_failure_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = CacheService()
    monkeypatch.setattr("app.cache.service.get_redis", lambda: FakeRedis())
    before = (REDIS_HITS._value.get(), REDIS_MISSES._value.get())
    errors = REDIS_ERRORS.labels("get")._value.get()

    assert await cache.get("hit") == b"value"
    assert await cache.get("miss") is None
    assert await cache.get("error") is None

    assert REDIS_HITS._value.get() == before[0] + 1
    assert REDIS_MISSES._value.get() == before[1] + 1
    assert REDIS_ERRORS.labels("get")._value.get() == errors + 1


@pytest.mark.asyncio
async def test_external_provider_success_timeout_and_http_error_metrics() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(500 if request.url.path == "/error" else 200)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        success_before = EXTERNAL_REQUESTS.labels("test", "lookup", "success")._value.get()
        error_before = EXTERNAL_REQUESTS.labels("test", "lookup", "error")._value.get()
        timeout_before = EXTERNAL_ERRORS.labels("test", "lookup", "ReadTimeout")._value.get()
        assert (
            await instrumented_httpx_request(
                client, "GET", "https://provider.test/ok", provider="test", operation="lookup"
            )
        ).status_code == 200
        assert (
            await instrumented_httpx_request(
                client,
                "GET",
                "https://provider.test/error",
                provider="test",
                operation="lookup",
            )
        ).status_code == 500
        with pytest.raises(httpx.ReadTimeout):
            await instrumented_httpx_request(
                client,
                "GET",
                "https://provider.test/timeout",
                provider="test",
                operation="lookup",
            )

    assert EXTERNAL_REQUESTS.labels("test", "lookup", "success")._value.get() == success_before + 1
    assert EXTERNAL_REQUESTS.labels("test", "lookup", "error")._value.get() == error_before + 2
    assert EXTERNAL_ERRORS.labels("test", "lookup", "ReadTimeout")._value.get() == timeout_before + 1
    assert b"password" not in generate_latest(REGISTRY)


def test_db_pool_metrics_hooks_use_public_pool_api(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = main_module.engine.sync_engine.pool
    monkeypatch.setattr(pool, "size", lambda: 7)
    monkeypatch.setattr(pool, "checkedout", lambda: 3)
    monkeypatch.setattr(pool, "checkedin", lambda: 4)
    monkeypatch.setattr(pool, "overflow", lambda: 1)
    from app.db.session import update_pool_metrics

    update_pool_metrics()
    body = generate_latest(REGISTRY).decode()
    assert "db_pool_size 7.0" in body
    assert "db_pool_checked_out 3.0" in body
    assert "db_pool_checked_in 4.0" in body
    assert "db_pool_overflow 1.0" in body

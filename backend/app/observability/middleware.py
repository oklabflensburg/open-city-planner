import logging
import re
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

from app.observability.context import bind_request_context, clear_request_context, route_var
from app.observability.logging import log_event, trace_context
from app.observability.metrics import HTTP_DURATION, HTTP_IN_PROGRESS, HTTP_REQUESTS

logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")


def valid_request_id(value: str | None) -> bool:
    return bool(value and REQUEST_ID_RE.fullmatch(value))


def request_id_for(value: str | None) -> str:
    return value if valid_request_id(value) else str(uuid.uuid4())


def route_template(request: Request) -> str:
    cache_key = "_observability_route_patterns"
    patterns = getattr(request.app.state, cache_key, None)
    if patterns is None:
        patterns = []
        for template, operations in request.app.openapi().get("paths", {}).items():
            expression = re.sub(r"\\\{[^/]+\\\}", "[^/]+", re.escape(template))
            methods = frozenset(method.upper() for method in operations)
            patterns.append((re.compile(f"^{expression}$"), template, methods))
        setattr(request.app.state, cache_key, patterns)
    for expression, template, methods in patterns:
        if request.method in methods and expression.fullmatch(request.url.path):
            return template
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match is Match.FULL:
            path = getattr(route, "path", None)
            if path:
                return path
    return "unmatched"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, metrics_enabled: bool, metrics_path: str) -> None:
        super().__init__(app)
        self.metrics_enabled = metrics_enabled
        self.metrics_path = metrics_path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request_id_for(request.headers.get(REQUEST_ID_HEADER))
        tokens = bind_request_context(request_id)
        route = route_template(request)
        route_var.set(route)
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        measure = self.metrics_enabled and request.url.path != self.metrics_path
        if measure:
            HTTP_IN_PROGRESS.labels(request.method, route).inc()
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration = time.perf_counter() - started
            if measure:
                HTTP_IN_PROGRESS.labels(request.method, route).dec()
                HTTP_REQUESTS.labels(request.method, route, f"{status_code // 100}xx").inc()
                HTTP_DURATION.labels(request.method, route).observe(duration)
            trace_id, span_id = trace_context()
            fields = {
                "method": request.method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 3),
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
            }
            log_event(
                logger,
                logging.ERROR if status_code >= 500 else logging.INFO,
                "http_request_completed",
                **fields,
            )
            clear_request_context(tokens)

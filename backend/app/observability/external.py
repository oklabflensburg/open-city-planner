import time
from typing import Any

import httpx

from app.observability.metrics import EXTERNAL_DURATION, EXTERNAL_ERRORS, EXTERNAL_REQUESTS


async def instrumented_httpx_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    provider: str,
    operation: str,
    **kwargs: Any,
) -> httpx.Response:
    started = time.perf_counter()
    try:
        request_method = getattr(client, method.lower(), None)
        if request_method is None:
            response = await client.request(method, url, **kwargs)
        else:
            response = await request_method(url, **kwargs)
    except Exception as exc:
        EXTERNAL_REQUESTS.labels(provider, operation, "error").inc()
        EXTERNAL_ERRORS.labels(provider, operation, type(exc).__name__).inc()
        raise
    finally:
        EXTERNAL_DURATION.labels(provider, operation).observe(time.perf_counter() - started)
    status_code = int(getattr(response, "status_code", 200))
    result = "success" if status_code < 400 else "error"
    EXTERNAL_REQUESTS.labels(provider, operation, result).inc()
    if status_code >= 400:
        EXTERNAL_ERRORS.labels(provider, operation, f"HTTP_{status_code}").inc()
    return response

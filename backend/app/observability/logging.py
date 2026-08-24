import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from app.observability.context import request_id_var, route_var
from app.observability.redaction import redact, redact_text

STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def trace_context() -> tuple[str | None, str | None]:
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None, None
    return f"{context.trace_id:032x}", f"{context.span_id:016x}"


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str, environment: str, release_sha: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment
        self.release_sha = release_sha

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = trace_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "service": self.service,
            "environment": self.environment,
            "release_sha": self.release_sha,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        context_values = {
            "request_id": request_id_var.get(),
            "trace_id": trace_id,
            "span_id": span_id,
            "route": route_var.get(),
        }
        payload.update({key: value for key, value in context_values.items() if value})
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in STANDARD_RECORD_FIELDS and not key.startswith("_")
        }
        payload.update(redact(extras))
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Error"
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


def configure_logging(
    *, level: str, service: str, environment: str, release_sha: str, json_logs: bool
) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(
            JsonFormatter(service=service, environment=environment, release_sha=release_sha)
        )
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(level, event, extra={"event": event, **redact(fields)})


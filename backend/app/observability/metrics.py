import time
from contextlib import contextmanager
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter(
    "http_requests_total", "Completed HTTP requests", ("method", "route", "status_class"), registry=REGISTRY
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=REGISTRY,
)
HTTP_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "Requests currently running", ("method", "route"), registry=REGISTRY
)

DB_POOL_SIZE = Gauge("db_pool_size", "Configured SQLAlchemy pool size", registry=REGISTRY)
DB_POOL_CAPACITY = Gauge(
    "db_pool_capacity", "Configured SQLAlchemy pool plus maximum overflow", registry=REGISTRY
)
DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out", "Checked out DB connections", registry=REGISTRY)
DB_POOL_AVAILABLE = Gauge("db_pool_checked_in", "Connections available in the DB pool", registry=REGISTRY)
DB_POOL_OVERFLOW = Gauge("db_pool_overflow", "Current DB pool overflow", registry=REGISTRY)
DB_POOL_WAIT = Histogram(
    "db_pool_wait_seconds", "Time waiting to acquire a database connection", registry=REGISTRY
)
DB_CONNECTION_ERRORS = Counter(
    "db_connection_errors_total", "Database connection failures", registry=REGISTRY
)

REDIS_OPERATIONS = Counter(
    "redis_operations_total", "Redis operations", ("operation", "result"), registry=REGISTRY
)
REDIS_DURATION = Histogram(
    "redis_operation_duration_seconds", "Redis operation latency", ("operation",), registry=REGISTRY
)
REDIS_ERRORS = Counter("redis_errors_total", "Redis errors", ("operation",), registry=REGISTRY)
REDIS_HITS = Counter("redis_cache_hits_total", "Redis cache hits", registry=REGISTRY)
REDIS_MISSES = Counter("redis_cache_misses_total", "Redis cache misses", registry=REGISTRY)
REDIS_PAYLOAD = Histogram(
    "redis_payload_bytes", "Redis payload size", ("operation",), buckets=(64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304), registry=REGISTRY
)
REDIS_AVAILABLE = Gauge("redis_available", "Redis health status (1=available)", registry=REGISTRY)

EXTERNAL_REQUESTS = Counter(
    "external_requests_total", "External provider requests", ("provider", "operation", "result"), registry=REGISTRY
)
EXTERNAL_DURATION = Histogram(
    "external_request_duration_seconds", "External provider latency", ("provider", "operation"), registry=REGISTRY
)
EXTERNAL_ERRORS = Counter(
    "external_request_errors_total", "External provider errors", ("provider", "operation", "error_type"), registry=REGISTRY
)

OUTBOX_PENDING = Gauge("outbox_pending", "Pending outbox entries", ("outbox_type",), registry=REGISTRY)
OUTBOX_OLDEST_AGE = Gauge(
    "outbox_oldest_age_seconds", "Age of oldest pending outbox entry", ("outbox_type",), registry=REGISTRY
)
OUTBOX_PROCESSED = Counter(
    "outbox_processed_total", "Processed outbox entries", ("outbox_type",), registry=REGISTRY
)
OUTBOX_FAILED = Counter("outbox_failed_total", "Failed outbox entries", ("outbox_type",), registry=REGISTRY)
OUTBOX_RETRY = Counter("outbox_retry_total", "Retried outbox entries", ("outbox_type",), registry=REGISTRY)

EVENT_OUTBOX_PENDING = Gauge(
    "event_outbox_pending", "Incomplete domain events", registry=REGISTRY
)
EVENT_OUTBOX_OLDEST_AGE = Gauge(
    "event_outbox_oldest_age_seconds",
    "Age of the oldest incomplete domain event",
    registry=REGISTRY,
)
EVENT_DISPATCH = Counter(
    "event_dispatch_total",
    "Domain event handler dispatches",
    ("event_name", "handler_id", "result"),
    registry=REGISTRY,
)
EVENT_DISPATCH_FAILURES = Counter(
    "event_dispatch_failures_total",
    "Failed domain event handler dispatches",
    ("event_name", "handler_id"),
    registry=REGISTRY,
)
EVENT_DEAD_LETTER = Counter(
    "event_dead_letter_total",
    "Domain event deliveries moved to dead letter",
    ("event_name", "handler_id"),
    registry=REGISTRY,
)
EVENT_HANDLER_DURATION = Histogram(
    "event_handler_duration_seconds",
    "Domain event handler duration",
    ("event_name", "handler_id", "result"),
    registry=REGISTRY,
)

JOB_RUNS = Counter("job_runs_total", "Background job runs", ("job_name",), registry=REGISTRY)
JOB_FAILURES = Counter("job_failures_total", "Background job failures", ("job_name",), registry=REGISTRY)
JOB_DURATION = Histogram(
    "job_duration_seconds", "Background job duration", ("job_name",), registry=REGISTRY
)
JOB_LAST_SUCCESS = Gauge(
    "job_last_success_timestamp_seconds", "Last successful job completion", ("job_name",), registry=REGISTRY
)
OSM_REPLICATION_LAG = Gauge(
    "osm_replication_lag_seconds", "Age of the newest locally imported OSM feature", registry=REGISTRY
)
BUILD = Info("build", "Running Stadtplaner release", registry=REGISTRY)


def set_build_info(*, release_sha: str, version: str, environment: str) -> None:
    BUILD.info({"release_sha": release_sha, "version": version, "environment": environment})


@contextmanager
def external_request(provider: str, operation: str):
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        EXTERNAL_REQUESTS.labels(provider, operation, "error").inc()
        EXTERNAL_ERRORS.labels(provider, operation, type(exc).__name__).inc()
        raise
    else:
        EXTERNAL_REQUESTS.labels(provider, operation, "success").inc()
    finally:
        EXTERNAL_DURATION.labels(provider, operation).observe(time.perf_counter() - started)


def observe_redis(operation: str, started: float, *, result: str, payload: Any = None) -> None:
    REDIS_OPERATIONS.labels(operation, result).inc()
    REDIS_DURATION.labels(operation).observe(time.perf_counter() - started)
    if isinstance(payload, (bytes, bytearray, str)):
        REDIS_PAYLOAD.labels(operation).observe(len(payload))

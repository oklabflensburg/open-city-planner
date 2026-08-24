# Production observability

Stadtplaner uses vendor-neutral JSON logs, Prometheus/OpenMetrics metrics and optional OpenTelemetry traces. The application has no dependency on Grafana, a collector or a hosted service to start or serve requests.

## Architecture and correlation

Nginx creates the edge `X-Request-ID` and forwards it to Nuxt and FastAPI. Direct requests may supply a safe 1–96 character ASCII token; both applications replace missing, oversized or control-character values with a UUID. Nuxt forwards the ID on SSR API requests. FastAPI returns it, and CORS exposes the response header to browser code.

FastAPI stores request ID and route template in `ContextVar`s. OpenTelemetry independently propagates W3C `traceparent` and `tracestate`; active trace and span IDs are added to JSON logs. The intended chain is `browser -> nginx -> Nuxt SSR -> FastAPI -> PostgreSQL/HTTP provider`.

## Structured logs and privacy

Production emits one JSON `http_request_completed` event per request. It contains timestamp, level, service, environment, release SHA, logger, request ID, trace/span IDs when active, method, route template, status and duration. 5xx is error-level; 4xx remains info-level. Background jobs emit `job_completed` or `job_failed` with the same deployment metadata. Nginx access logs are JSON and omit headers and bodies.

The formatter recursively redacts keys containing password, token, secret, authorization, cookie, API key, CSRF, recovery code, OTP/TOTP, email or prompt. It also removes emails, bearer values and JWT-shaped strings from messages. Request/response bodies, query strings, SQL bind values and recipient addresses are never observability fields. Assistant provider responses and raw prompts are redacted unless the explicit `ASSISTANT_QUERY_LOGGING` diagnostic switch is enabled; production defaults it to false.

```bash
journalctl -u stadtplaner-api -o cat
journalctl -u stadtplaner-frontend -o cat
journalctl -u stadtplaner-api -o cat | jq 'select(.request_id == "edge-id")'
```

## Metrics

`GET /metrics` is enabled by default and uses low-cardinality labels only. Nginx denies it except for loopback and configured monitoring CIDRs.

| Area | Metrics | Labels |
| --- | --- | --- |
| HTTP RED | `http_requests_total`, `http_request_duration_seconds`, `http_requests_in_progress` | method, route template, status class |
| Database | `db_pool_size`, `db_pool_capacity`, `db_pool_checked_out`, `db_pool_checked_in`, `db_pool_overflow`, `db_pool_wait_seconds`, `db_connection_errors_total` | none |
| Redis | `redis_operations_total`, `redis_operation_duration_seconds`, `redis_errors_total`, `redis_cache_hits_total`, `redis_cache_misses_total`, `redis_payload_bytes`, `redis_available` | bounded operation/result |
| Providers | `external_requests_total`, `external_request_duration_seconds`, `external_request_errors_total` | provider, bounded operation/result/error type |
| Outboxes | `outbox_pending`, `outbox_oldest_age_seconds`, `outbox_processed_total`, `outbox_failed_total`, `outbox_retry_total` | email, polygon or social |
| Jobs | `job_runs_total`, `job_failures_total`, `job_duration_seconds`, `job_last_success_timestamp_seconds` | fixed job name |
| OSM | `osm_replication_lag_seconds` | none |
| Build | `build_info` | release SHA, version, environment |

Request IDs, user IDs, emails, slugs, provider URLs, search text and queries are never metric labels. Job/outbox/OSM values survive oneshot processes as Prometheus textfiles in `OBSERVABILITY_TEXTFILE_DIR`; configure node_exporter's textfile collector for that directory.

## Tracing

Tracing is disabled unless both `OTEL_ENABLED=true` and an `OTEL_EXPORTER_OTLP_ENDPOINT` are configured. FastAPI, HTTPX and SQLAlchemy are instrumented. SQL bind values are not captured and SQL commenter injection is disabled. The OTLP gRPC exporter uses a batch processor, so an unavailable collector does not block application startup or synchronously export requests.

```dotenv
OTEL_ENABLED=true
OTEL_SERVICE_NAME=stadtplaner-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

## Prometheus, Grafana and alerts

Use `deploy/observability/prometheus/prometheus.example.yml` as a starting point and add the Prometheus host network to `stadtplaner_metrics_allowed_cidrs`. Load `deploy/observability/prometheus/alerts.yml` and import `deploy/observability/grafana/stadtplaner-overview.json`. The readiness alert uses the Prometheus blackbox exporter; the API scrape alone cannot prove readiness semantics.

For a complete self-hosted installation, use the separate Ansible monitoring
playbook described in [monitoring-deployment.md](monitoring-deployment.md). It
installs Prometheus, Grafana, Node Exporter and Blackbox Exporter, provisions the
dashboard and datasource, and keeps every listener on loopback by default.

| Signal | Threshold / duration | Severity | Runbook |
| --- | --- | --- | --- |
| Readiness | failed 10m | critical | `readiness-down.md` |
| 5xx | >5% 10m / >15% 5m | warning / critical | `high-5xx-rate.md` |
| p95 latency | >2s 15m | warning | `high-5xx-rate.md` |
| DB pool | >90% 10m | warning | `db-pool-saturation.md` |
| Redis | unavailable 10m | warning | `redis-down.md` |
| Outbox | >100 pending or oldest >1h for 15m | warning | `outbox-backlog.md` |
| Job | failure observed for 5m | warning | `background-job-failure.md` |
| OSM | lag >2h for 15m | warning | `osm-replication-stale.md` |

## Service objectives

These are pragmatic civic-tech targets, measured monthly and reviewed after enough production data exists:

- API availability: 99.5%, using successful readiness probes; announced maintenance is reported separately.
- Standard read-request p95 latency: below 1 second. The alert starts at 2 seconds to avoid noisy paging.
- API server-error ratio: below 1%. Alerts start at 5% because traffic can be low.
- Readiness: continuously probed every 30 seconds.
- OSM freshness: normally below two hours behind the imported replication timestamp.

## Configuration and release metadata

| Variable | Production default | Purpose |
| --- | --- | --- |
| `LOG_FORMAT` | `json` | `json` or development-only `text` |
| `LOG_LEVEL` | `INFO` | application log level |
| `METRICS_ENABLED` | `true` | expose the internal metrics handler |
| `METRICS_PATH` | `/metrics` | handler path; keep Nginx config aligned |
| `OBSERVABILITY_TEXTFILE_DIR` | `/data/stadtplaner/observability` | persistent oneshot metrics |
| `OTEL_ENABLED` | `false` | optional tracing switch |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | empty | collector endpoint, never hardcoded |
| `STADTPLANER_RELEASE_SHA` | injected by Ansible | exact deployed Git commit |

`/health/info` publishes only version, exact release SHA and environment. `build_info`, backend logs, frontend SSR logs and background logs use the same Ansible-resolved commit.

## Local development and troubleshooting

Start without a monitoring backend; `/metrics` remains directly available on the development API. Generate traffic with `curl -H 'X-Request-ID: local-smoke' http://127.0.0.1:8000/health/live`, then inspect the response header, JSON line and metric counter. If telemetry is absent, check feature flags first; a stopped Prometheus, Grafana or OTLP collector must not affect health. If cardinality grows unexpectedly, inspect route/provider/operation labels and remove dynamic values before deployment.

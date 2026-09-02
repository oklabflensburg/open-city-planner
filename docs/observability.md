# Production observability

Stadtplaner uses vendor-neutral JSON logs, Prometheus/OpenMetrics metrics and OpenTelemetry traces. Production deployment requires a reachable collector and Tempo backend; the application runtime remains fail-open and has no synchronous dependency on either service while serving requests.

## Architecture and correlation

Nginx creates the edge `X-Request-ID` and forwards it to Nuxt and FastAPI. Direct requests may supply a safe 1–96 character ASCII token; both applications replace missing, oversized or control-character values with a UUID. Nuxt forwards the ID on SSR API requests. FastAPI returns it, and CORS exposes the response header to browser code.

FastAPI stores request ID and route template in `ContextVar`s. OpenTelemetry independently propagates W3C `traceparent` and `tracestate`; active trace and span IDs are added to JSON logs. The intended chain is `browser -> nginx -> Nuxt SSR -> FastAPI -> PostgreSQL/HTTP provider`.

## Structured logs and privacy

Production emits one JSON `http_request_completed` event per request. It contains timestamp, level, service, environment, release SHA, logger, request ID, trace/span IDs when active, method, route template, status and duration. 5xx is error-level; 4xx remains info-level. Background jobs emit `job_completed` or `job_failed` with the same deployment metadata. Nginx access logs are JSON and omit headers and bodies.

The formatter recursively redacts keys containing password, token, secret, authorization, cookie, API key, CSRF, recovery code, OTP/TOTP, email or prompt. It also removes emails, bearer values and JWT-shaped strings from messages. Request/response bodies, query strings, SQL bind values and recipient addresses are never observability fields. The same redaction boundary applies to data emitted by installed modules.

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

Development tracing stays disabled by default. Production configuration requires `OTEL_ENABLED=true`, a credential-free HTTP(S) origin with an explicit port, and the supported `grpc` protocol. FastAPI, HTTPX and SQLAlchemy are instrumented. SQL bind values are not captured and SQL commenter injection is disabled. The OTLP gRPC exporter uses a batch processor, so an unavailable collector does not block application startup or synchronously export requests.

```dotenv
OTEL_ENABLED=true
OTEL_SERVICE_NAME=stadtplaner-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
```

The normal production playbook installs OpenTelemetry Collector Contrib
`0.153.0` and Grafana Tempo `2.10.7` from checksum-verified upstream archives.
The Collector receives gRPC on `127.0.0.1:4317`, exposes health only on
`127.0.0.1:13133/health/status`, and forwards to Tempo on the separate local
gRPC port `4319`. Tempo serves readiness and queries on `127.0.0.1:3200` and
retains local trace blocks for 14 days. None of these ports is proxied by Nginx.

Both processes run under dedicated, non-login accounts: `stadtplaner-otel` and
`stadtplaner-tempo`. Their configuration is split between
`/etc/stadtplaner/otel/collector/collector.yml` and
`/etc/stadtplaner/otel/tempo/tempo.yml`. Each directory is `0750` and each file
is `0640`, with only the matching service group receiving read access. The
shared `/etc/stadtplaner` and `/etc/stadtplaner/otel` directories remain
restricted; POSIX ACL entries grant each service account traverse-only (`--x`)
access instead of making directories containing application secrets globally
searchable or readable.

Before systemd is restarted, Ansible checks file readability as each service
account and validates both effective configurations with the pinned binaries.
It then polls Tempo readiness through the expected initial HTTP 503 phase until
HTTP 200 and verifies the loopback listeners plus Collector health. Static
permission or configuration errors therefore fail at preflight rather than
appearing later as an OTLP port timeout and restart loop.

The parent-based 10% sampler respects an upstream sampled decision. The deploy
smoke request intentionally supplies a sampled W3C context, polls Tempo for the
current `service.version` (the exact Ansible release SHA), and uses
`/health/ready` so the trace includes the FastAPI server span and an instrumented
database child span. A missing export triggers the existing atomic application
rollback. No fixed sleep is used.

## Prometheus, Grafana and alerts

Use `deploy/observability/prometheus/prometheus.example.yml` as a starting point and add the Prometheus host network to `stadtplaner_metrics_allowed_cidrs`. Load `deploy/observability/prometheus/alerts.yml` and import `deploy/observability/grafana/stadtplaner-overview.json`. The readiness and Collector alerts use the Prometheus blackbox exporter; the API scrape alone cannot prove readiness semantics. The monitoring playbook provisions Tempo as the `stadtplaner-tempo` Grafana datasource.

For a complete self-hosted installation, use the separate Ansible monitoring
playbook described in [monitoring-deployment.md](monitoring-deployment.md). It
installs Prometheus, Grafana, Node Exporter and Blackbox Exporter, provisions the
dashboard and datasource, and keeps every listener on loopback by default.

| Signal | Threshold / duration | Severity | Runbook |
| --- | --- | --- | --- |
| Readiness | failed 10m | critical | `readiness-down.md` |
| OTel Collector | failed 5m | critical | `otel-collector-down.md` |
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
| `OTEL_ENABLED` | `true` | required for production; development remains `false` |
| `OTEL_SERVICE_NAME` | `stadtplaner-api` | standard `service.name` resource attribute |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://127.0.0.1:4317` | local production Collector |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | only supported exporter protocol |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | preserves parent sampling decisions |
| `OTEL_TRACES_SAMPLER_ARG` | `0.1` | production root sampling ratio |
| `STADTPLANER_RELEASE_SHA` | injected by Ansible | exact deployed Git commit |

`/health/info` publishes only version, exact release SHA and environment. `build_info`, backend logs, frontend SSR logs and background logs use the same Ansible-resolved commit.

## Local development and troubleshooting

Start local development without a monitoring backend; `/metrics` remains directly available on the development API. Generate traffic with `curl -H 'X-Request-ID: local-smoke' http://127.0.0.1:8000/health/live`, then inspect the response header, JSON line and metric counter. If production telemetry is absent, check `systemctl status stadtplaner-otel-collector stadtplaner-tempo`, both local health URLs and the [Collector runbook](runbooks/otel-collector-down.md). A Collector outage after deployment must not affect API health or request latency. If cardinality grows unexpectedly, inspect route/provider/operation labels and remove dynamic values before deployment.

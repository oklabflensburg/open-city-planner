# Readiness down

Signal: `probe_success{job="stadtplaner-readiness"} == 0` for 10 minutes. Severity: critical.

Meaning: `/health/ready` cannot confirm the API's PostgreSQL and required Redis dependencies. Liveness may still be healthy.

First checks: request `/health/live` and `/health/ready`; inspect `systemctl status stadtplaner-api postgresql redis-server`; correlate the response `X-Request-ID` with API JSON logs.

Diagnosis: inspect `database` and `redis` in readiness output, `db_connection_errors_total`, `redis_available`, pool gauges and `journalctl -u stadtplaner-api`. Check disk, connections and recent release SHA.

Mitigation: restore the failed dependency, free exhausted DB connections, or restart only the unhealthy dependency. Restart the API only after dependency health is understood. Roll back to the previous release if failures began with a deployment.

Escalation: notify the production operator immediately when readiness remains down after dependency recovery or data integrity may be affected.


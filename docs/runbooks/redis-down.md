# Redis down

Signal: `redis_available == 0` for 10 minutes. Severity: warning.

Meaning: caching and production security counters are unavailable. Production requires Redis, while optional development mode can fall back to the database.

First checks: inspect `/health/ready`, `systemctl status redis-server`, `redis-cli ping`, `redis_errors_total` and Redis latency. Review API logs without printing the Redis URL.

Diagnosis: check memory pressure, connection limits, disk persistence and network binding. Determine whether the outage followed a deploy or host event.

Mitigation: restore Redis capacity/service and verify `redis_available` returns to 1. Restart the API only if clients fail to reconnect. Never log or paste Redis credentials.

Escalation: escalate immediately if readiness is down, authentication rate limiting is affected, or Redis data recovery is required.


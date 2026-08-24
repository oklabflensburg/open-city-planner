# Database pool saturation

Signal: `db_pool_checked_out / db_pool_capacity > 0.9` for 10 minutes. Severity: warning.

Meaning: API workers are close to exhausting their configured PostgreSQL connections; requests may wait or time out.

First checks: inspect checked-out, available, overflow, `db_pool_wait_seconds`, DB connection errors and API latency. Check PostgreSQL `pg_stat_activity` and server connection limits.

Diagnosis: correlate slow routes/traces, long transactions and blocked queries. Confirm the sum across all API processes fits PostgreSQL capacity before changing pool settings.

Mitigation: stop a runaway job, resolve locks/slow queries, or restart a leaking worker after capturing evidence. Increase pool capacity only with database headroom. Roll back a release that introduced persistent growth.

Escalation: involve the database operator when saturation persists, blockers cannot be safely cancelled, or recovery risks an active transaction.


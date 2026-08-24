# Outbox backlog

Signal: `outbox_pending > 100` or `outbox_oldest_age_seconds > 3600` for 15 minutes. Severity: warning.

Meaning: email, polygon notification or social work is not keeping pace. Recipient addresses and payloads are intentionally absent from metrics.

First checks: identify `outbox_type`; inspect its timer/service status, `outbox_failed_total`, `outbox_retry_total`, job failures and provider metrics.

Diagnosis: run the relevant CLI in its normal environment with a small limit, inspect redacted JSON logs, database status/attempt counts and provider availability. Do not dump message bodies.

Mitigation: restore the provider, re-enable the timer, or process a bounded batch. Preserve idempotency and existing retry/dead-letter rules; do not mass-reset rows without a backup.

Escalation: involve the service owner when dead letters rise, messages are time-critical, or replay could duplicate external side effects.


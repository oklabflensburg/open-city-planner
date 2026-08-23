# High 5xx rate or latency

Signal: 5xx ratio above 5% for 10 minutes (warning), above 15% for 5 minutes (critical), or p95 latency above 2 seconds for 15 minutes.

Meaning: users are receiving server errors or the API is degraded. A single low-volume error does not trigger the alert.

First checks: split `http_requests_total` and latency by route; inspect DB, Redis and provider panels; query JSON logs for `event="http_request_completed"` with `status_code>=500` and the active `release_sha`.

Diagnosis: follow a representative `request_id`/`trace_id`; inspect child DB/provider spans and `external_request_errors_total`. Compare onset with deployment and job activity.

Mitigation: isolate the failing route/provider, reduce nonessential load, restore dependencies, or roll back the active release. Do not disable logging or alerts to hide the signal.

Escalation: escalate critical rates immediately; include route, release SHA, request ID, trace ID and first failing timestamp.


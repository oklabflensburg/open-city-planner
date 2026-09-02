# Background job failure

Signal: `increase(job_failures_total[15m]) > 0` for 5 minutes. Severity: warning.

Meaning: a systemd timer job exited unsuccessfully. `job_name` identifies OSM replication, email processing, event delivery or an installed module job.

First checks: run `systemctl status <job>.timer <job>.service`, inspect the last invocation with `journalctl -u <job>.service`, and compare `job_last_success_timestamp_seconds`.

Diagnosis: use the structured `job_failed` log, release SHA, dependency and provider metrics. Validate environment-file readability and writable paths without printing secrets.

Mitigation: correct the dependency/configuration and start the oneshot service once. Avoid overlapping manual and scheduled runs. Roll back when the first failure aligns with a release.

Escalation: escalate repeated failures or missed data-delivery windows with job name, exit status, release SHA and redacted error type.

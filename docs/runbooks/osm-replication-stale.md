# OSM replication stale

Signal: `osm_replication_lag_seconds > 7200` for 15 minutes. Severity: warning.

Meaning: the newest locally published OSM snapshot is more than two hours behind its replication timestamp.

First checks: inspect `stadtplaner-osm-update.timer/service`, free disk, network access to the configured replication URL and the last successful job timestamp.

Diagnosis: inspect OSM update JSON logs and phase output, replication state files and PostgreSQL staging/import health. Confirm the upstream replication feed itself is current. Module-owned postprocessing has separate job status.

Mitigation: fix disk/network/database issues and run one non-overlapping update. Use the documented initial import only when replication state cannot be recovered; take a backup before destructive reinitialization.

Escalation: involve the OSM/data operator after two missed hourly runs, corrupted state, or any need for a full reimport.

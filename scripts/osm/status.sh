#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

echo "Replication status:"
osm2pgsql-replication status "${replication_db_args[@]}" --json
echo "Published Stadtplaner state:"
psql -X --no-psqlrc --tuples-only --field-separator=' | ' -c \
  "SELECT sequence, osm_timestamp, last_success_at, inserted_count, updated_count, deleted_count, CASE WHEN now()-osm_timestamp <= interval '3 hours' THEN 'HEALTHY' WHEN now()-osm_timestamp <= interval '12 hours' THEN 'LAGGING' ELSE 'FAILED' END FROM osm_sync_state WHERE singleton"
if command -v systemctl >/dev/null; then
  systemctl --no-pager --full status stadtplaner-osm-update.timer || true
fi

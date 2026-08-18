#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

lock_file="${OSM_LOCK_FILE:-$OSM_DATA_DIR/update.lock}"
exec 9>"$lock_file"
if ! flock -n 9; then
  echo "OSM_UPDATE_SKIPPED reason=already_running"
  exit 0
fi

pg_isready -q || { echo "OSM_UPDATE_FAILED reason=database_unavailable" >&2; exit 69; }
psql -X --no-password -v ON_ERROR_STOP=1 -Atc "SELECT 1" >/dev/null || {
  echo "OSM_UPDATE_FAILED reason=database_authentication" >&2
  exit 77
}
started_at="$(date +%s)"
echo "OSM_UPDATE_START started_at=$(date --iso-8601=seconds)"
echo "OSM_UPDATE_STATUS_BEFORE"
osm2pgsql-replication status "${replication_db_args[@]}" --json

osm2pgsql-replication update \
  "${replication_db_args[@]}" \
  --max-diff-size "$OSM_MAX_DIFF_MB" \
  --post-processing "$SCRIPT_DIR/post-process.sh" \
  -- \
  --output flex \
  --style "$OSM_STYLE"

echo "OSM_UPDATE_STATUS_AFTER"
osm2pgsql-replication status "${replication_db_args[@]}" --json
echo "OSM_UPDATE_SUCCESS duration_seconds=$(($(date +%s) - started_at))"

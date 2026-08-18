#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

: "${OSM_PBF_URL:=https://download.geofabrik.de/europe/germany/schleswig-holstein-latest.osm.pbf}"
: "${OSM_PBF_MD5_URL:=${OSM_PBF_URL}.md5}"

extract_dir="$OSM_DATA_DIR/extracts"
pbf="$extract_dir/schleswig-holstein-latest.osm.pbf"
checksum="$pbf.md5"
mkdir -p "$extract_dir" "$OSM_DATA_DIR/replication" "$OSM_DATA_DIR/tmp" "$OSM_DATA_DIR/logs"

lock_file="${OSM_LOCK_FILE:-$OSM_DATA_DIR/update.lock}"
exec 9>"$lock_file"
if ! flock -n 9; then
  echo "OSM_INITIAL_FAILED reason=update_already_running" >&2
  exit 75
fi

for command in curl flock md5sum osmium osm2pgsql osm2pgsql-replication psql pg_isready; do
  command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 69; }
done

pg_isready -q || { echo "PostgreSQL is not ready" >&2; exit 69; }
psql -X --no-password -v ON_ERROR_STOP=1 -Atc "SELECT 1" >/dev/null || {
  echo "PostgreSQL authentication failed; check the service user's .pgpass" >&2
  exit 77
}
[[ -r "$OSM_STYLE" ]] || { echo "Flex style is not readable: $OSM_STYLE" >&2; exit 66; }

echo "OSM_INITIAL_DOWNLOAD url=$OSM_PBF_URL"
curl --fail --location --retry 3 --output "$pbf.part" "$OSM_PBF_URL"
curl --fail --location --retry 3 --output "$checksum" "$OSM_PBF_MD5_URL"
expected_hash="$(awk 'NR == 1 { print $1 }' "$checksum")"
actual_hash="$(md5sum "$pbf.part" | awk '{ print $1 }')"
[[ "$expected_hash" == "$actual_hash" ]] || { echo "PBF checksum mismatch" >&2; exit 65; }
mv "$pbf.part" "$pbf"

osmium fileinfo "$pbf"
pbf_timestamp="$(osmium fileinfo -g header.option.osmosis_replication_timestamp "$pbf")"
[[ -n "$pbf_timestamp" ]] || { echo "PBF has no replication timestamp" >&2; exit 65; }
echo "OSM_INITIAL_SOURCE timestamp=$pbf_timestamp"

postgis_ready="$(psql -X --no-password -v ON_ERROR_STOP=1 -Atc \
  "SELECT count(*) FROM pg_extension WHERE extname='postgis'")"
[[ "$postgis_ready" == "1" ]] || {
  echo "PostGIS is missing; install it once as a PostgreSQL administrator" >&2
  exit 77
}

owned_schemas="$(psql -X --no-password -v ON_ERROR_STOP=1 -Atc \
  "SELECT count(*) FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner
   WHERE n.nspname IN ('$OSM_OUTPUT_SCHEMA','$OSM_MIDDLE_SCHEMA')
     AND r.rolname=current_user")"
[[ "$owned_schemas" == "2" ]] || {
  echo "Import schemas are missing or not owned by $PGUSER; run the documented admin setup" >&2
  exit 77
}

started_at="$(date +%s)"
osm2pgsql \
  --create \
  --slim \
  -d "$PGDATABASE" \
  -U "$PGUSER" \
  -H "$PGHOST" \
  -P "$PGPORT" \
  --prefix "$OSM_PREFIX" \
  --schema "$OSM_OUTPUT_SCHEMA" \
  --middle-schema "$OSM_MIDDLE_SCHEMA" \
  --output flex \
  --style "$OSM_STYLE" \
  --cache "$OSM_CACHE_MB" \
  "$pbf"

application_db_role="${OSM_APPLICATION_DB_ROLE:-$(
  cd "$OSM_BACKEND_DIR"
  "$OSM_BACKEND_DIR/.venv/bin/python" - <<'PY'
from sqlalchemy.engine import make_url

from app.core.config import get_settings

print(make_url(get_settings().database_url).username or "")
PY
)}"
if [[ ! "$application_db_role" =~ ^[a-z_][a-z0-9_]*$ ]]; then
  echo "Invalid or missing application database role: $application_db_role" >&2
  exit 64
fi
psql -X --no-password -v ON_ERROR_STOP=1 \
  --set=app_role="$application_db_role" \
  --set=import_role="$PGUSER" \
  --set=output_schema="$OSM_OUTPUT_SCHEMA" <<'SQL'
GRANT USAGE ON SCHEMA :"output_schema" TO :"app_role";
GRANT SELECT ON ALL TABLES IN SCHEMA :"output_schema" TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"import_role" IN SCHEMA :"output_schema"
  GRANT SELECT ON TABLES TO :"app_role";
SQL

# Geofabrik's PBF is a coherent regional snapshot. Its own compatible diffs are
# daily only; use its exact timestamp to start the official minutely stream
# without losing the interval between snapshot creation and initialization.
osm2pgsql-replication init \
  "${replication_db_args[@]}" \
  --server "$OSM_REPLICATION_URL" \
  --start-at "$pbf_timestamp"

cd "$OSM_BACKEND_DIR"
"$OSM_BACKEND_DIR/.venv/bin/alembic" -c "$OSM_BACKEND_DIR/alembic.ini" upgrade head
"$OSM_BACKEND_DIR/.venv/bin/python" -m app.cli.postprocess_osm \
  --timestamp "$pbf_timestamp" \
  --municipality "$OSM_MUNICIPALITY"

echo "OSM_INITIAL_SUCCESS duration_seconds=$(($(date +%s) - started_at)) timestamp=$pbf_timestamp"

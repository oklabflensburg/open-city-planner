#!/usr/bin/env bash

set -euo pipefail

OSM_ENV_FILE="${OSM_ENV_FILE:-/etc/stadtplaner/osm-sync.env}"
if [[ -r "$OSM_ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$OSM_ENV_FILE"
  set +a
fi

: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=open_city_map}"
: "${PGUSER:=osm}"
: "${OSM_DATA_DIR:=/var/lib/stadtplaner/osm}"
: "${OSM_REPOSITORY:=/opt/git/open-city-planner}"
: "${OSM_BACKEND_DIR:=${OSM_REPOSITORY}/backend}"
: "${OSM_OUTPUT_SCHEMA:=osm_import}"
: "${OSM_MIDDLE_SCHEMA:=osm_middle}"
: "${OSM_PREFIX:=stadtplaner_osm}"
: "${OSM_STYLE:=${OSM_REPOSITORY}/scripts/osm/osm.lua}"
: "${OSM_REPLICATION_URL:=https://planet.openstreetmap.org/replication/minute}"
: "${OSM_MUNICIPALITY:=Flensburg}"
: "${OSM_CACHE_MB:=1024}"
: "${OSM_MAX_DIFF_MB:=100}"

export PGHOST PGPORT PGDATABASE PGUSER
export OSM_OUTPUT_SCHEMA OSM_BBOX_WEST OSM_BBOX_SOUTH OSM_BBOX_EAST OSM_BBOX_NORTH

for identifier in "$OSM_OUTPUT_SCHEMA" "$OSM_MIDDLE_SCHEMA" "$OSM_PREFIX"; do
  if [[ ! "$identifier" =~ ^[a-z_][a-z0-9_]*$ ]]; then
    echo "Invalid PostgreSQL identifier: $identifier" >&2
    exit 64
  fi
done

replication_db_args=(
  --database "$PGDATABASE"
  --username "$PGUSER"
  --host "$PGHOST"
  --port "$PGPORT"
  --prefix "$OSM_PREFIX"
  --schema "$OSM_OUTPUT_SCHEMA"
  --middle-schema "$OSM_MIDDLE_SCHEMA"
)

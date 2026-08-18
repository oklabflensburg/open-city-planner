#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

sequence="${1:-}"
timestamp="${2:-}"
[[ "$sequence" =~ ^[0-9]+$ ]] || { echo "Missing/invalid replication sequence" >&2; exit 64; }
[[ -n "$timestamp" ]] || { echo "Missing replication timestamp" >&2; exit 64; }

cd "$OSM_BACKEND_DIR"
"$OSM_BACKEND_DIR/.venv/bin/python" -m app.cli.postprocess_osm \
  --sequence "$sequence" \
  --timestamp "$timestamp" \
  --municipality "$OSM_MUNICIPALITY" \
  --verbose

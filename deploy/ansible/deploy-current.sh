#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

git fetch origin main
SHA="${STADTPLANER_DEPLOY_REF:-$(git rev-parse origin/main)}"
VAULT_FILE="${STADTPLANER_VAULT_FILE:-}"

cd deploy/ansible
args=(playbooks/deploy.yml)

if [[ -n "$VAULT_FILE" ]]; then
  args+=( -e "@${VAULT_FILE}" --ask-vault-pass )
fi

printf 'Deploying Open City Planner commit %s\n' "$SHA"
# Keep the requested release authoritative if the external vault or additional
# command-line arguments contain a stale ref. For repeated -e options, the last
# value wins.
exec ansible-playbook "${args[@]}" "$@" -e "stadtplaner_deploy_ref=${SHA}"

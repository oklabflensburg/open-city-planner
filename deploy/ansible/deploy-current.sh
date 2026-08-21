#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

git fetch origin main
SHA="${STADTPLANER_DEPLOY_REF:-$(git rev-parse origin/main)}"
VAULT_FILE="${STADTPLANER_VAULT_FILE:-}"

cd deploy/ansible
args=(playbooks/deploy.yml -e "stadtplaner_deploy_ref=${SHA}")

if [[ -n "$VAULT_FILE" ]]; then
  args+=( -e "@${VAULT_FILE}" --ask-vault-pass )
fi

printf 'Deploying Open City Planner commit %s\n' "$SHA"
exec ansible-playbook "${args[@]}" "$@"

#!/usr/bin/env bash
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "${temporary_directory}"' EXIT

prefix="OCM_TEST_SECRET_"
suffix="ABCDEFGHIJKLMNOPQRST"
printf '%s%s\n' "${prefix}" "${suffix}" > "${temporary_directory}/must-block.txt"
printf '%s%s # gitleaks:allow\n' "${prefix}" "${suffix}" > "${temporary_directory}/allowed.txt"

if gitleaks dir --no-banner --redact=100 --config "${repository}/.gitleaks.toml" \
  "${temporary_directory}/must-block.txt" >/dev/null 2>&1; then
  echo "Gitleaks failed to block the synthetic test secret." >&2
  exit 1
fi

gitleaks dir --no-banner --redact=100 --config "${repository}/.gitleaks.toml" \
  "${temporary_directory}/allowed.txt" >/dev/null
echo "Gitleaks negative and allowlist fixtures passed."

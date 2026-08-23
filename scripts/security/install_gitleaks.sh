#!/usr/bin/env bash
set -euo pipefail

GITLEAKS_VERSION="8.30.1"
GITLEAKS_LINUX_X64_SHA256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "The pinned Gitleaks installer currently supports Linux x86_64 only." >&2
  exit 1
fi

install_directory="${1:?usage: install_gitleaks.sh INSTALL_DIRECTORY}"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "${temporary_directory}"' EXIT
archive="${temporary_directory}/gitleaks.tar.gz"

curl --fail --silent --show-error --location \
  "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
  --output "${archive}"
echo "${GITLEAKS_LINUX_X64_SHA256}  ${archive}" | sha256sum --check --status
tar -xzf "${archive}" -C "${temporary_directory}" gitleaks
install -d "${install_directory}"
install -m 0755 "${temporary_directory}/gitleaks" "${install_directory}/gitleaks"
"${install_directory}/gitleaks" version

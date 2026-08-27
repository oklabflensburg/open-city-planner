"""Validate that backend runtime modules match the frontend build inventory."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

MODULE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def dotenv_value(path: Path, key: str) -> str | None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        candidate, value = line.split("=", 1)
        if candidate.strip() != key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value
    return None


def required_dotenv_value(path: Path, key: str) -> str:
    value = dotenv_value(path, key)
    if value is None:
        raise ValueError(f"required module setting {key} is missing")
    return value


def module_ids(value: str, *, versions_allowed: bool) -> set[str]:
    modules: set[str] = set()
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        module_id, separator, version = entry.partition("@")
        if not MODULE_ID_PATTERN.fullmatch(module_id):
            raise ValueError(f"invalid module ID {module_id!r}")
        if separator and (not versions_allowed or not version or "@" in version):
            raise ValueError(f"invalid module inventory entry {entry!r}")
        modules.add(module_id)
    return modules


def validate_module_inventory(backend_env: Path, frontend_env: Path) -> None:
    backend_modules = module_ids(
        required_dotenv_value(backend_env, "ENABLED_MODULES"), versions_allowed=False
    )
    frontend_inventory = module_ids(
        required_dotenv_value(frontend_env, "OCP_BACKEND_MODULES"),
        versions_allowed=True,
    )
    if backend_modules == frontend_inventory:
        return

    missing_from_frontend = sorted(backend_modules - frontend_inventory)
    missing_from_backend = sorted(frontend_inventory - backend_modules)
    details = []
    if missing_from_frontend:
        details.append("missing from OCP_BACKEND_MODULES: " + ", ".join(missing_from_frontend))
    if missing_from_backend:
        details.append("missing from ENABLED_MODULES: " + ", ".join(missing_from_backend))
    raise ValueError("module inventory mismatch; " + "; ".join(details))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend_env", type=Path)
    parser.add_argument("frontend_env", type=Path)
    args = parser.parse_args()
    validate_module_inventory(args.backend_env, args.frontend_env)
    print("Backend and frontend module inventories match.")


if __name__ == "__main__":
    main()

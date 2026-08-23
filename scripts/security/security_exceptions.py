"""Load and validate time-bounded security exceptions."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = ("id", "scanner", "reason", "owner", "expires", "mitigation", "review_date")
SCANNERS = {"backend-dependency", "frontend-dependency", "codeql", "secret-scan"}


class ExceptionPolicyError(ValueError):
    """Raised when the security exception file violates policy."""


def _parse_date(value: Any, field: str, finding_id: str) -> date:
    if not isinstance(value, str):
        raise ExceptionPolicyError(f"{finding_id}: {field} must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ExceptionPolicyError(f"{finding_id}: {field} must use YYYY-MM-DD") from exc


def load_exceptions(path: Path, *, today: date | None = None) -> list[dict[str, Any]]:
    current_date = today or datetime.now(UTC).date()
    try:
        document = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ExceptionPolicyError(f"cannot read valid YAML from {path}: {exc}") from exc

    if not isinstance(document, dict) or document.get("version") != 1:
        raise ExceptionPolicyError("security exception policy must be a mapping with version: 1")
    entries = document.get("exceptions")
    if not isinstance(entries, list):
        raise ExceptionPolicyError("security exception policy must contain an exceptions list")

    seen: set[str] = set()
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ExceptionPolicyError(f"exception {index} must be a mapping")
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            raise ExceptionPolicyError(f"exception {index} is missing: {', '.join(missing)}")
        finding_id = entry["id"]
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise ExceptionPolicyError(f"exception {index}: id must be a non-empty string")
        if finding_id in seen:
            raise ExceptionPolicyError(f"duplicate security exception id: {finding_id}")
        seen.add(finding_id)

        scanner = entry["scanner"]
        if scanner not in SCANNERS:
            raise ExceptionPolicyError(
                f"{finding_id}: scanner must be one of {', '.join(sorted(SCANNERS))}"
            )
        for field in ("reason", "owner", "mitigation"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ExceptionPolicyError(f"{finding_id}: {field} must be a non-empty string")

        expires = _parse_date(entry["expires"], "expires", finding_id)
        review_date = _parse_date(entry["review_date"], "review_date", finding_id)
        if expires < current_date:
            raise ExceptionPolicyError(f"{finding_id}: exception expired on {expires.isoformat()}")
        if review_date > expires:
            raise ExceptionPolicyError(f"{finding_id}: review_date must not be after expires")

    return entries


def active_ids(path: Path, scanner: str) -> set[str]:
    return {entry["id"] for entry in load_exceptions(path) if entry["scanner"] == scanner}

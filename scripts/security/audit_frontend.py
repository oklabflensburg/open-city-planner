#!/usr/bin/env python3
"""Audit frozen frontend production dependencies with the shared severity policy."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .security_exceptions import ExceptionPolicyError, active_ids
except ImportError:  # Support direct script execution.
    from security_exceptions import ExceptionPolicyError, active_ids


BLOCKING_SEVERITIES = {"high", "critical"}
ADVISORY_ID = re.compile(r"(?:GHSA-[\w-]+|CVE-\d{4}-\d+)", re.IGNORECASE)


def identifiers(advisory: dict[str, Any]) -> set[str]:
    values: list[Any] = [
        advisory.get("github_advisory_id"),
        advisory.get("id"),
        advisory.get("url"),
        *(advisory.get("cves") or []),
    ]
    found: set[str] = set()
    for value in values:
        if value is None:
            continue
        matches = ADVISORY_ID.findall(str(value))
        if matches:
            found.update(match.upper() for match in matches)
        elif isinstance(value, int) or str(value).isdigit():
            found.add(str(value))
    return found


def blocking_advisories(document: dict[str, Any], ignored: set[str]) -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    advisories = document.get("advisories", {})
    if not isinstance(advisories, dict):
        raise TypeError("pnpm audit response does not contain an advisories mapping")
    for key, advisory in advisories.items():
        if not isinstance(advisory, dict):
            continue
        finding_severity = str(advisory.get("severity", "unknown")).lower()
        if finding_severity not in BLOCKING_SEVERITIES:
            continue
        ids = identifiers(advisory) or {str(key)}
        if ids & ignored:
            continue
        canonical_id = next(
            (value for value in sorted(ids) if value.startswith(("GHSA-", "CVE-"))),
            min(ids),
        )
        findings.append((canonical_id, str(advisory.get("module_name", "unknown")), finding_severity))
    return findings


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    try:
        ignored = active_ids(
            repository / ".github/security-exceptions.yml", "frontend-dependency"
        )
    except ExceptionPolicyError as exc:
        print(f"Security exception policy failed: {exc}", file=sys.stderr)
        return 1

    audit = subprocess.run(
        ["pnpm", "audit", "--prod", "--audit-level", "high", "--json"],
        cwd=repository / "frontend",
        check=False,
        text=True,
        capture_output=True,
    )
    try:
        document = json.loads(audit.stdout)
        findings = blocking_advisories(document, ignored)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Frontend audit failed to produce a valid report: {exc}", file=sys.stderr)
        if audit.stderr:
            print(audit.stderr.strip(), file=sys.stderr)
        return 1
    if findings:
        print("Blocking frontend dependency findings:", file=sys.stderr)
        for finding_id, package, finding_severity in findings:
            print(f"- {finding_id}: {package} ({finding_severity})", file=sys.stderr)
        return 1
    if audit.returncode not in (0, 1):
        print("Frontend audit failed because the advisory service was unavailable.", file=sys.stderr)
        return audit.returncode
    print("Frontend production dependency audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

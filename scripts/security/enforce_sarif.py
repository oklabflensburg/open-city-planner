#!/usr/bin/env python3
"""Block High/Critical SARIF findings unless a current exception exists."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .security_exceptions import ExceptionPolicyError, active_ids
except ImportError:  # Support direct script execution.
    from security_exceptions import ExceptionPolicyError, active_ids


def severity(rule: dict[str, Any], result: dict[str, Any]) -> tuple[str, bool]:
    properties = rule.get("properties", {})
    raw_score = properties.get("security-severity") or properties.get("security_severity")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = None
    if score is not None:
        if score >= 9.0:
            return "critical", True
        if score >= 7.0:
            return "high", True
        if score >= 4.0:
            return "medium", False
        return "low", False
    level = result.get("level") or rule.get("defaultConfiguration", {}).get("level")
    return ("high", True) if level == "error" else (str(level or "unknown"), False)


def _secret_finding_id(rule_id: str, result: dict[str, Any]) -> str:
    location = result.get("locations", [{}])[0].get("physicalLocation", {})
    uri = location.get("artifactLocation", {}).get("uri", "unknown-path")
    line = location.get("region", {}).get("startLine", 0)
    commit = result.get("partialFingerprints", {}).get("commitSha", "working-tree")
    return f"{rule_id}@{commit}:{uri}:{line}"


def _redact_finding_id(finding_id: str) -> str:
    digest = hashlib.sha256(finding_id.encode("utf-8")).hexdigest()
    return f"id:{digest[:12]}"


def blocking_findings(
    paths: list[Path], ignored: set[str], *, scanner: str = "codeql"
) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for path in paths:
        document = json.loads(path.read_text())
        for run in document.get("runs", []):
            rules = {
                rule.get("id"): rule
                for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
            }
            for result in run.get("results", []):
                rule_id = result.get("ruleId", "unknown-rule")
                finding_id = (
                    _secret_finding_id(rule_id, result) if scanner == "secret-scan" else rule_id
                )
                finding_severity, blocks = severity(rules.get(rule_id, {}), result)
                if scanner == "secret-scan":
                    finding_severity, blocks = "high", True
                if blocks and finding_id not in ignored:
                    findings.append((finding_id, finding_severity))
    return findings


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--scanner", required=True, choices=("codeql", "secret-scan"))
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        ignored = active_ids(repository / ".github/security-exceptions.yml", args.scanner)
        findings = blocking_findings(args.paths, ignored, scanner=args.scanner)
    except (ExceptionPolicyError, OSError, json.JSONDecodeError) as exc:
        print(f"SARIF policy evaluation failed: {exc}", file=sys.stderr)
        return 1
    if findings:
        print("Blocking SARIF findings:", file=sys.stderr)
        for rule_id, finding_severity in sorted(set(findings)):
            print(f"- {_redact_finding_id(rule_id)}: {finding_severity}", file=sys.stderr)
        return 1
    print(f"SARIF policy passed for {args.scanner}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

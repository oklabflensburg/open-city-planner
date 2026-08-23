#!/usr/bin/env python3
"""Audit the frozen set of production Python dependencies."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from .security_exceptions import ExceptionPolicyError, active_ids
except ImportError:  # Support direct script execution.
    from security_exceptions import ExceptionPolicyError, active_ids


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    backend = repository / "backend"
    policy = repository / ".github/security-exceptions.yml"
    try:
        ignored = sorted(active_ids(policy, "backend-dependency"))
    except ExceptionPolicyError as exc:
        print(f"Security exception policy failed: {exc}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as directory:
        requirements = Path(directory) / "production-requirements.txt"
        exported = subprocess.run(
            [
                "uv", "export", "--frozen", "--no-dev", "--no-default-groups",
                "--no-emit-project", "--format", "requirements.txt", "--output-file",
                str(requirements),
            ],
            cwd=backend,
            check=False,
            stdout=subprocess.DEVNULL,
        )
        if exported.returncode:
            return exported.returncode
        command = [
            "uv", "run", "--frozen", "--extra", "security", "pip-audit",
            "--requirement", str(requirements), "--require-hashes", "--disable-pip",
            "--progress-spinner", "off",
        ]
        for finding_id in ignored:
            command.extend(("--ignore-vuln", finding_id))
        return subprocess.run(command, cwd=backend, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

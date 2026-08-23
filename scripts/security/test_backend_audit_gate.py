#!/usr/bin/env python3
"""Prove that pip-audit rejects a dynamically generated vulnerable fixture."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    package = "urllib" + "3"
    version = "1.24." + "1"
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory) / "audit-negative-fixture.txt"
        fixture.write_text(f"{package}=={version}\n")
        audit = subprocess.run(
            [
                "uv", "run", "--frozen", "--extra", "security", "pip-audit",
                "--requirement", str(fixture), "--no-deps", "--disable-pip",
                "--progress-spinner", "off",
            ],
            cwd=repository / "backend",
            check=False,
        )
    if audit.returncode == 1:
        print("Backend audit negative fixture was blocked.")
        return 0
    if audit.returncode == 0:
        print("pip-audit accepted the intentionally vulnerable fixture.", file=sys.stderr)
    else:
        print(f"pip-audit failed unexpectedly with exit code {audit.returncode}.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the repository's security exception policy."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .security_exceptions import ExceptionPolicyError, load_exceptions
except ImportError:  # Support direct script execution.
    from security_exceptions import ExceptionPolicyError, load_exceptions


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=repository / ".github/security-exceptions.yml",
    )
    args = parser.parse_args()
    try:
        entries = load_exceptions(args.path)
    except ExceptionPolicyError as exc:
        print(f"Security exception policy failed: {exc}", file=sys.stderr)
        return 1
    print(f"Security exception policy passed ({len(entries)} active exceptions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

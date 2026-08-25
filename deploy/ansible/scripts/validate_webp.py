#!/usr/bin/env python3
"""Validate the byte-level envelope of a downloaded WebP smoke image."""

from __future__ import annotations

import argparse
from pathlib import Path


def validate_webp(data: bytes, minimum_size: int) -> None:
    if len(data) < minimum_size:
        raise ValueError(f"WebP is too small: {len(data)} bytes (minimum {minimum_size})")
    if data[:4] != b"RIFF":
        raise ValueError("WebP is missing the RIFF header")
    if data[8:12] != b"WEBP":
        raise ValueError("WebP is missing the WEBP signature")
    declared_size = int.from_bytes(data[4:8], byteorder="little") + 8
    if declared_size != len(data):
        raise ValueError(
            f"WebP RIFF size mismatch: header declares {declared_size} bytes, got {len(data)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--minimum-size", type=int, default=64)
    args = parser.parse_args()
    try:
        validate_webp(args.path.read_bytes(), args.minimum_size)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"invalid WebP smoke response: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

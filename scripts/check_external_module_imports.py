#!/usr/bin/env python3
"""Reject private Host imports in an installed or checked-out Python module."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

PUBLIC_HOST_IMPORTS = ("app.platform.modules.sdk",)


@dataclass(frozen=True, slots=True)
class PrivateHostImport:
    source: Path
    imported: str
    line: int


def private_host_imports(root: Path) -> tuple[PrivateHostImport, ...]:
    violations: list[PrivateHostImport] = []
    for source in sorted(root.rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            names: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = (node.module,)
            for imported in names:
                if imported == "app" or (
                    imported.startswith("app.")
                    and not imported.startswith(PUBLIC_HOST_IMPORTS)
                ):
                    violations.append(PrivateHostImport(source, imported, node.lineno))
    return tuple(violations)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module_source", type=Path)
    args = parser.parse_args()
    root = args.module_source.resolve()
    if not root.is_dir():
        parser.error(f"module source is not a directory: {root}")
    violations = private_host_imports(root)
    for violation in violations:
        print(
            f"::error file={violation.source},line={violation.line},"
            "title=ARCH-BE-INSTALLED-001::"
            f"Private Host import {violation.imported}; use app.platform.modules.sdk."
        )
    return int(bool(violations))


if __name__ == "__main__":
    raise SystemExit(main())

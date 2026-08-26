#!/usr/bin/env python3
"""Fail-closed architecture check for backend module boundaries."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.platform.modules.import_boundaries import (
    find_cross_module_import_violations,
    find_host_settings_import_violations,
)

RULES = ROOT / "architecture/module-contract-rules.json"
BASELINE = ROOT / "architecture/module-boundary-baseline.json"
HOST_FORBIDDEN = (
    "app.api",
    "app.auth",
    "app.cli",
    "app.models",
    "app.schemas",
    "app.security",
    "app.services",
)
MODULE_PRIVATE = (
    "app.api",
    "app.auth",
    "app.cache",
    "app.cli",
    "app.core",
    "app.db",
    "app.models",
    "app.observability",
    "app.platform.modules",
    "app.schemas",
    "app.security",
    "app.services",
)


@dataclass(frozen=True, slots=True)
class Violation:
    rule: str
    source: str
    target: str
    line: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.rule, self.source, self.target)


def imported_names(source: Path, python_root: Path) -> list[tuple[str, int]]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    relative = source.relative_to(python_root)
    current_package = relative.parent.parts
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = max(len(current_package) - (node.level - 1), 0)
                suffix = tuple(node.module.split(".")) if node.module else ()
                base_parts = (*current_package[:keep], *suffix)
                base = ".".join(base_parts)
            else:
                base = node.module or ""
            if base:
                found.append((base, node.lineno))
                found.extend(
                    (f"{base}.{alias.name}", node.lineno)
                    for alias in node.names
                    if alias.name != "*"
                )
    return found


def forbidden_imports(
    source: Path,
    python_root: Path,
    prefixes: tuple[str, ...],
) -> list[tuple[str, int]]:
    matches = [
        item for item in imported_names(source, python_root) if item[0].startswith(prefixes)
    ]
    selected: list[tuple[str, int]] = []
    for target, line in sorted(matches, key=lambda item: (item[1], len(item[0]))):
        if any(line == prior_line and target.startswith(f"{prior}.") for prior, prior_line in selected):
            continue
        selected.append((target, line))
    return selected


def scan_backend(root: Path = ROOT) -> tuple[Violation, ...]:
    backend = root / "backend"
    violations: list[Violation] = []
    host_root = backend / "app/platform/modules"
    if host_root.exists():
        for source in sorted(host_root.rglob("*.py")):
            for target, line in forbidden_imports(source, backend, HOST_FORBIDDEN):
                violations.append(_violation(root, "ARCH-BE-HOST-001", source, target, line))

    for modules_root, package_prefix in (
        (backend / "app/modules", "app.modules"),
        (backend / "modules", "modules"),
    ):
        if not modules_root.exists():
            continue
        for item in find_cross_module_import_violations(
            modules_root, package_prefix=package_prefix
        ):
            violations.append(
                _violation(
                    root,
                    "ARCH-BE-MODULE-001",
                    item.source,
                    item.imported_module,
                    item.line,
                )
            )
        for item in find_host_settings_import_violations(modules_root):
            violations.append(
                _violation(
                    root,
                    "ARCH-BE-PRIVATE-001",
                    item.source,
                    item.imported_module,
                    item.line,
                )
            )
        for source in sorted(modules_root.rglob("*.py")):
            for target, line in forbidden_imports(source, backend, MODULE_PRIVATE):
                if not target.startswith("app.platform.modules.sdk"):
                    violations.append(
                        _violation(root, "ARCH-BE-PRIVATE-001", source, target, line)
                    )
    return tuple(sorted(set(violations), key=lambda item: (item.source, item.line, item.rule)))


def load_baseline(root: Path = ROOT) -> frozenset[tuple[str, str, str]]:
    rules_data = json.loads((root / RULES.relative_to(ROOT)).read_text(encoding="utf-8"))
    baseline_data = json.loads((root / BASELINE.relative_to(ROOT)).read_text(encoding="utf-8"))
    if rules_data.get("version") != 1 or baseline_data.get("version") != 1:
        raise ValueError("Architecture rule and baseline versions must be 1.")
    known = {rule["id"] for rule in rules_data.get("rules", [])}
    entries = baseline_data.get("entries")
    if not isinstance(entries, list):
        raise TypeError("Architecture baseline entries must be a list.")
    keys: set[tuple[str, str, str]] = set()
    for entry in entries:
        key = (entry.get("rule"), entry.get("source"), entry.get("target"))
        if key[0] not in known:
            raise ValueError(f"Unknown baseline rule: {key[0]}")
        if not all(isinstance(value, str) and value and "*" not in value for value in key):
            raise ValueError("Baseline rule, source and target must be exact non-wildcard strings.")
        if not re.fullmatch(r"#\d+", entry.get("tracking_issue", "")):
            raise ValueError("Every baseline entry needs a tracking_issue like #123.")
        if not str(entry.get("reason", "")).strip():
            raise ValueError("Every baseline entry needs a reason.")
        if not (root / key[1]).is_file():
            raise ValueError(f"Baseline source does not exist: {key[1]}")
        if key in keys:
            raise ValueError(f"Duplicate baseline entry: {key}")
        keys.add(key)
    return frozenset(keys)


def active_violations(root: Path = ROOT) -> tuple[Violation, ...]:
    baseline = load_baseline(root)
    return tuple(item for item in scan_backend(root) if item.key not in baseline)


def _violation(root: Path, rule: str, source: Path, target: str, line: int) -> Violation:
    return Violation(rule, source.relative_to(root).as_posix(), target, line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        violations = active_violations(args.root.resolve())
    except (OSError, TypeError, ValueError, json.JSONDecodeError, SyntaxError) as error:
        print(f"Architecture check configuration error: {error}", file=sys.stderr)
        return 2
    for item in violations:
        guidance = {
            "ARCH-BE-HOST-001": "Use a registration entry point or public contribution contract.",
            "ARCH-BE-MODULE-001": "Use the provider module's public contracts namespace.",
            "ARCH-BE-PRIVATE-001": "Use the matching ModuleContext/SDK port.",
        }[item.rule]
        print(
            f"::error file={item.source},line={item.line},title={item.rule}::"
            f"Forbidden import {item.target}. {guidance}"
        )
    if violations:
        print(f"Backend module architecture check failed with {len(violations)} violation(s).")
        return 1
    print("Backend module architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

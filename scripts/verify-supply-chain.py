#!/usr/bin/env python3
"""Verify immutable dependency, workflow, and deployment inputs."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST_IMAGE = re.compile(r"@sha256:[0-9a-f]{64}$")
EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def files(root: Path, directory: str, suffixes: tuple[str, ...]) -> list[Path]:
    base = root / directory
    return sorted(path for path in base.rglob("*") if path.is_file() and path.suffix in suffixes)


def verify(root: Path, *, check_lock: bool = True) -> list[str]:
    errors: list[str] = []
    workflow_files = files(root, ".github/workflows", (".yml", ".yaml"))

    for path in workflow_files:
        relative = path.relative_to(root)
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            action = re.search(r"^\s*-?\s*uses:\s*([^\s#]+)", line)
            if action:
                value = action.group(1)
                if value.startswith("./"):
                    continue
                if "@" not in value or not FULL_SHA.fullmatch(value.rsplit("@", 1)[1]):
                    errors.append(f"{relative}:{line_number}: external action is not pinned to a full SHA: {value}")

            image = re.search(r"^\s*image:\s*([^\s#]+)", line)
            if image and not DIGEST_IMAGE.search(image.group(1)):
                errors.append(f"{relative}:{line_number}: service image is not pinned by SHA-256 digest: {image.group(1)}")

    lockfile = root / "backend/uv.lock"
    if not lockfile.is_file():
        errors.append("backend/uv.lock: missing backend lockfile")

    pyproject_path = root / "backend/pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())
    uv_required = pyproject.get("tool", {}).get("uv", {}).get("required-version", "")
    if not re.fullmatch(r"==\d+\.\d+\.\d+", uv_required):
        errors.append("backend/pyproject.toml: tool.uv.required-version must be an exact == version")
    build_requirements = pyproject.get("build-system", {}).get("requires", [])
    build_constraints = pyproject.get("tool", {}).get("uv", {}).get("build-constraint-dependencies", [])
    if not build_requirements or any(not re.search(r"==\d+\.\d+\.\d+$", item) for item in build_requirements):
        errors.append("backend/pyproject.toml: build-system requirements must use exact versions")
    if sorted(build_requirements) != sorted(build_constraints):
        errors.append("backend/pyproject.toml: build requirements must also be uv build constraints")

    python_version = (root / ".python-version").read_text().strip()
    node_version = (root / ".node-version").read_text().strip()
    if not EXACT_VERSION.fullmatch(python_version):
        errors.append(".python-version: expected an exact Python patch version")
    if not EXACT_VERSION.fullmatch(node_version):
        errors.append(".node-version: expected an exact Node.js patch version")

    package = json.loads((root / "frontend/package.json").read_text())
    package_manager = package.get("packageManager", "")
    pnpm_match = re.fullmatch(r"pnpm@(\d+\.\d+\.\d+)(?:\+sha512\.[0-9a-f]+)?", package_manager)
    if not pnpm_match:
        errors.append("frontend/package.json: packageManager must pin an exact pnpm version")
    pnpm_version = pnpm_match.group(1) if pnpm_match else ""
    for path in workflow_files:
        text = path.read_text()
        setup_count = text.count("pnpm/action-setup@")
        version_count = len(re.findall(rf"^\s+version:\s*{re.escape(pnpm_version)}\s*$", text, re.MULTILINE))
        if setup_count != version_count:
            errors.append(f"{path.relative_to(root)}: every pnpm setup must use packageManager version {pnpm_version}")

    requirements = (root / "deploy/ansible/requirements.txt").read_text().strip().splitlines()
    ansible_input = (root / "deploy/ansible/requirements.in").read_text().strip()
    if not re.fullmatch(r"ansible-core==\d+\.\d+\.\d+", ansible_input):
        errors.append("deploy/ansible/requirements.in: ansible-core must be pinned with ==X.Y.Z")
    ansible_pins = [line for line in requirements if line.startswith("ansible-core")]
    if len(ansible_pins) != 1 or not re.fullmatch(r"ansible-core==\d+\.\d+\.\d+ \\", ansible_pins[0]):
        errors.append("deploy/ansible/requirements.txt: ansible-core must be pinned with ==X.Y.Z")
    if "--hash=sha256:" not in "\n".join(requirements):
        errors.append("deploy/ansible/requirements.txt: hashed transitive lock is required")
    if ansible_pins and not ansible_pins[0].startswith(ansible_input + " "):
        errors.append("deploy/ansible/requirements.txt: lock does not match requirements.in")

    policy_files = workflow_files + files(root, "deploy/ansible", (".yml", ".yaml"))
    for path in policy_files:
        text = path.read_text()
        relative = path.relative_to(root)
        if re.search(r"(?:python\s+-m\s+)?pip\s+install\s+-e(?:\s|$)", text):
            errors.append(f"{relative}: editable pip installation bypasses backend/uv.lock")
        if "ansible-core>" in text or "ansible-core<" in text or "ansible-core~=" in text:
            errors.append(f"{relative}: ansible-core uses a version range")

    runtime_defaults = (root / "deploy/ansible/roles/stadtplaner_runtime/defaults/main.yml").read_text()
    expected_runtime_values = {
        "stadtplaner_python_version": python_version,
        "stadtplaner_node_version": node_version,
        "stadtplaner_pnpm_version": pnpm_version,
        "stadtplaner_uv_version": uv_required.removeprefix("=="),
    }
    for variable, version in expected_runtime_values.items():
        if not re.search(rf"^{re.escape(variable)}:\s*{re.escape(version)}\s*$", runtime_defaults, re.MULTILINE):
            errors.append(f"runtime defaults: {variable} must equal {version}")

    postgis_refs = []
    for path in workflow_files:
        postgis_refs.extend(re.findall(r"postgis/postgis:[^\s#]+", path.read_text()))
    if len(set(postgis_refs)) != 1 or len(postgis_refs) < 2:
        errors.append("workflows: every PostGIS service must use the same digest-pinned image")

    if check_lock and lockfile.is_file():
        uv_version = uv_required.removeprefix("==")
        try:
            installed = subprocess.run(
                ["uv", "--version"], cwd=root, check=False, text=True, capture_output=True
            )
        except FileNotFoundError:
            errors.append(f"uv {uv_version} is required to verify backend/uv.lock")
        else:
            if installed.returncode != 0 or not installed.stdout.strip().startswith(f"uv {uv_version} "):
                errors.append(f"uv {uv_version} is required; found {installed.stdout.strip() or 'unavailable'}")
            else:
                checked = subprocess.run(
                    ["uv", "lock", "--check"],
                    cwd=root / "backend",
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if checked.returncode != 0:
                    detail = (checked.stderr or checked.stdout).strip().splitlines()
                    errors.append(f"backend/uv.lock is stale: {detail[-1] if detail else 'uv lock --check failed'}")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = verify(root)
    if errors:
        print("Supply-chain verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Supply-chain verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

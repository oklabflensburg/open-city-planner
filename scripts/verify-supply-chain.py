#!/usr/bin/env python3
"""Verify immutable dependency, workflow, and deployment inputs."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

import tomllib

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST_IMAGE = re.compile(r"@sha256:[0-9a-f]{64}$")
EXACT_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
ACTION_VERSION = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
ACTION_USE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)(?:\s+#\s*(\S+))?\s*$")
DOCKER_ACTION = re.compile(r"^docker://.+@sha256:[0-9a-f]{64}$")

ActionRefResolver = Callable[[str, str], str]


def files(root: Path, directory: str, suffixes: tuple[str, ...]) -> list[Path]:
    base = root / directory
    return sorted(
        path for path in base.rglob("*") if path.is_file() and path.suffix in suffixes
    )


def resolve_github_tag_commit(repository: str, tag: str) -> str:
    """Resolve a GitHub tag to its commit, following annotated tag objects."""

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "open-city-planner-supply-chain-verifier",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get_json(url: str) -> dict[str, object]:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"GitHub API request failed for {repository}@{tag}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise TypeError(
                f"GitHub API returned an invalid response for {repository}@{tag}"
            )
        return payload

    encoded_tag = urllib.parse.quote(tag, safe="")
    payload = get_json(
        f"https://api.github.com/repos/{repository}/git/ref/tags/{encoded_tag}"
    )
    target = payload.get("object")
    for _ in range(5):
        if not isinstance(target, dict):
            break
        target_type = target.get("type")
        target_sha = target.get("sha")
        if not isinstance(target_sha, str) or not FULL_SHA.fullmatch(target_sha):
            break
        if target_type == "commit":
            return target_sha
        if target_type != "tag":
            break
        payload = get_json(
            f"https://api.github.com/repos/{repository}/git/tags/{target_sha}"
        )
        target = payload.get("object")
    raise RuntimeError(f"GitHub tag {repository}@{tag} did not resolve to a commit SHA")


def verify(
    root: Path,
    *,
    check_lock: bool = True,
    check_action_refs: bool = False,
    action_ref_resolver: ActionRefResolver = resolve_github_tag_commit,
) -> list[str]:
    errors: list[str] = []
    workflow_files = files(root, ".github/workflows", (".yml", ".yaml"))
    action_pins: dict[tuple[str, str, str], list[str]] = {}

    for path in workflow_files:
        relative = path.relative_to(root)
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            action = ACTION_USE.fullmatch(line)
            if action:
                value = action.group(1)
                if value.startswith("./"):
                    continue
                if value.startswith("docker://"):
                    if not DOCKER_ACTION.fullmatch(value):
                        errors.append(
                            f"{relative}:{line_number}: Docker action is not pinned by SHA-256 digest: {value}"
                        )
                    continue
                if "@" not in value or not FULL_SHA.fullmatch(value.rsplit("@", 1)[1]):
                    errors.append(
                        f"{relative}:{line_number}: external action is not pinned to a full SHA: {value}"
                    )
                    continue

                action_name, sha = value.rsplit("@", 1)
                repository_parts = action_name.split("/")
                if len(repository_parts) < 2:
                    errors.append(
                        f"{relative}:{line_number}: invalid external action repository: {action_name}"
                    )
                    continue
                if set(sha) == {"0"}:
                    errors.append(
                        f"{relative}:{line_number}: external action uses a known invalid/null SHA: {value}"
                    )

                version = action.group(2)
                if not version or not ACTION_VERSION.fullmatch(version):
                    errors.append(
                        f"{relative}:{line_number}: external action requires an exact version comment such as # v1.2.3: {value}"
                    )
                    continue
                repository = "/".join(repository_parts[:2])
                location = f"{relative}:{line_number}"
                action_pins.setdefault((repository, sha, version), []).append(location)

            image = re.search(r"^\s*image:\s*([^\s#]+)", line)
            if image and not DIGEST_IMAGE.search(image.group(1)):
                errors.append(
                    f"{relative}:{line_number}: service image is not pinned by SHA-256 digest: {image.group(1)}"
                )

    if check_action_refs:
        resolved_refs: dict[tuple[str, str], str] = {}
        for repository, sha, version in sorted(action_pins):
            ref = (repository, version)
            try:
                if ref not in resolved_refs:
                    resolved_refs[ref] = action_ref_resolver(*ref)
                resolved_sha = resolved_refs[ref]
            except (RuntimeError, TypeError) as exc:
                errors.append(str(exc))
                continue
            if sha != resolved_sha:
                locations = ", ".join(action_pins[(repository, sha, version)])
                errors.append(
                    f"{locations}: {repository}@{sha} does not match {version}, which resolves to {resolved_sha}"
                )

    lockfile = root / "backend/uv.lock"
    if not lockfile.is_file():
        errors.append("backend/uv.lock: missing backend lockfile")

    pyproject_path = root / "backend/pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())
    uv_required = pyproject.get("tool", {}).get("uv", {}).get("required-version", "")
    if not re.fullmatch(r"==\d+\.\d+\.\d+", uv_required):
        errors.append(
            "backend/pyproject.toml: tool.uv.required-version must be an exact == version"
        )
    build_requirements = pyproject.get("build-system", {}).get("requires", [])
    build_constraints = (
        pyproject.get("tool", {}).get("uv", {}).get("build-constraint-dependencies", [])
    )
    if not build_requirements or any(
        not re.search(r"==\d+\.\d+\.\d+$", item) for item in build_requirements
    ):
        errors.append(
            "backend/pyproject.toml: build-system requirements must use exact versions"
        )
    if sorted(build_requirements) != sorted(build_constraints):
        errors.append(
            "backend/pyproject.toml: build requirements must also be uv build constraints"
        )

    python_version = (root / ".python-version").read_text().strip()
    node_version = (root / ".node-version").read_text().strip()
    if not EXACT_VERSION.fullmatch(python_version):
        errors.append(".python-version: expected an exact Python patch version")
    if not EXACT_VERSION.fullmatch(node_version):
        errors.append(".node-version: expected an exact Node.js patch version")

    package = json.loads((root / "frontend/package.json").read_text())
    package_manager = package.get("packageManager", "")
    pnpm_match = re.fullmatch(
        r"pnpm@(\d+\.\d+\.\d+)(?:\+sha512\.[0-9a-f]+)?", package_manager
    )
    if not pnpm_match:
        errors.append(
            "frontend/package.json: packageManager must pin an exact pnpm version"
        )
    pnpm_version = pnpm_match.group(1) if pnpm_match else ""
    for path in workflow_files:
        text = path.read_text()
        setup_count = text.count("pnpm/action-setup@")
        version_count = len(
            re.findall(
                rf"^\s+version:\s*{re.escape(pnpm_version)}\s*$", text, re.MULTILINE
            )
        )
        if setup_count != version_count:
            errors.append(
                f"{path.relative_to(root)}: every pnpm setup must use packageManager version {pnpm_version}"
            )

    requirements = (
        (root / "deploy/ansible/requirements.txt").read_text().strip().splitlines()
    )
    ansible_input = (root / "deploy/ansible/requirements.in").read_text().strip()
    if not re.fullmatch(r"ansible-core==\d+\.\d+\.\d+", ansible_input):
        errors.append(
            "deploy/ansible/requirements.in: ansible-core must be pinned with ==X.Y.Z"
        )
    ansible_pins = [line for line in requirements if line.startswith("ansible-core")]
    if len(ansible_pins) != 1 or not re.fullmatch(
        r"ansible-core==\d+\.\d+\.\d+ \\", ansible_pins[0]
    ):
        errors.append(
            "deploy/ansible/requirements.txt: ansible-core must be pinned with ==X.Y.Z"
        )
    if "--hash=sha256:" not in "\n".join(requirements):
        errors.append(
            "deploy/ansible/requirements.txt: hashed transitive lock is required"
        )
    if ansible_pins and not ansible_pins[0].startswith(ansible_input + " "):
        errors.append(
            "deploy/ansible/requirements.txt: lock does not match requirements.in"
        )

    policy_files = workflow_files + files(root, "deploy/ansible", (".yml", ".yaml"))
    for path in policy_files:
        text = path.read_text()
        relative = path.relative_to(root)
        if re.search(r"(?:python\s+-m\s+)?pip\s+install\s+-e(?:\s|$)", text):
            errors.append(
                f"{relative}: editable pip installation bypasses backend/uv.lock"
            )
        if (
            "ansible-core>" in text
            or "ansible-core<" in text
            or "ansible-core~=" in text
        ):
            errors.append(f"{relative}: ansible-core uses a version range")

    runtime_defaults = (
        root / "deploy/ansible/roles/stadtplaner_runtime/defaults/main.yml"
    ).read_text()
    expected_runtime_values = {
        "stadtplaner_python_version": python_version,
        "stadtplaner_node_version": node_version,
        "stadtplaner_pnpm_version": pnpm_version,
        "stadtplaner_uv_version": uv_required.removeprefix("=="),
    }
    for variable, version in expected_runtime_values.items():
        if not re.search(
            rf"^{re.escape(variable)}:\s*{re.escape(version)}\s*$",
            runtime_defaults,
            re.MULTILINE,
        ):
            errors.append(f"runtime defaults: {variable} must equal {version}")

    postgis_refs = []
    for path in workflow_files:
        postgis_refs.extend(re.findall(r"postgis/postgis:[^\s#]+", path.read_text()))
    if len(set(postgis_refs)) != 1 or len(postgis_refs) < 2:
        errors.append(
            "workflows: every PostGIS service must use the same digest-pinned image"
        )

    if check_lock and lockfile.is_file():
        uv_version = uv_required.removeprefix("==")
        try:
            installed = subprocess.run(
                ["uv", "--version"],
                cwd=root,
                check=False,
                text=True,
                capture_output=True,
            )
        except FileNotFoundError:
            errors.append(f"uv {uv_version} is required to verify backend/uv.lock")
        else:
            if installed.returncode != 0 or not installed.stdout.strip().startswith(
                f"uv {uv_version} "
            ):
                errors.append(
                    f"uv {uv_version} is required; found {installed.stdout.strip() or 'unavailable'}"
                )
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
                    errors.append(
                        f"backend/uv.lock is stale: {detail[-1] if detail else 'uv lock --check failed'}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-action-refs",
        action="store_true",
        help="resolve each version comment through the GitHub API and compare it with the pinned SHA",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors = verify(root, check_action_refs=args.verify_action_refs)
    if errors:
        print("Supply-chain verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Supply-chain verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

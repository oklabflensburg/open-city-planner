"""Install, verify and configure separately distributed modules."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from app.cli import module_migrations
from app.core.config import BACKEND_ENV_FILE, get_settings
from app.platform.modules.bundle import (
    build_ocp_bundle,
    load_bundle_manifest,
    staged_ocp_bundle,
)
from app.platform.modules.installer import (
    DEFAULT_INSTALL_ROOT,
    EnablementEnvironment,
    ModuleInstaller,
    ModuleInstallerError,
    ModuleProvenance,
    ModuleSource,
    read_modules_lock,
)
from app.platform.modules.registry import (
    DEFAULT_REGISTRY_URL,
    REGISTRY_URL_ENV,
    ModuleRegistryClient,
    ModuleRegistryError,
)
from app.platform.modules.settings import read_module_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = REPOSITORY_ROOT / "frontend"
INSTALL_ROOT_ENV = "OCP_MODULE_INSTALL_ROOT"


def _install_root(value: str | None) -> Path:
    return Path(value or os.environ.get(INSTALL_ROOT_ENV, DEFAULT_INSTALL_ROOT))


def _installer(root: Path) -> ModuleInstaller:
    settings = get_settings()
    builtin_frontend = tuple(
        item.strip()
        for item in _frontend_enablement().split(",")
        if item.strip()
    )
    return ModuleInstaller(
        root,
        host_version=settings.api_version,
        builtin_enabled_ids=settings.enabled_module_list,
        builtin_frontend_enabled_ids=builtin_frontend,
        excluded_builtin_module_ids=settings.excluded_builtin_module_list,
        module_environment=read_module_environment(env_file=BACKEND_ENV_FILE),
        migration_preflight=lambda enabled_ids: _migration_preflight(root, enabled_ids),
        frontend_preflight=_frontend_preflight,
        frontend_package_preflight=lambda installed_root: _frontend_package_preflight(
            installed_root,
            settings.ocp_excluded_builtin_modules,
        ),
    )


def _registry_client(registry_url: str | None) -> ModuleRegistryClient:
    return ModuleRegistryClient(registry_url)


def _frontend_enablement() -> str:
    configured = os.environ.get("OCP_FRONTEND_MODULES")
    if configured is not None:
        return configured
    frontend_environment = FRONTEND_ROOT / ".env"
    if not frontend_environment.is_file():
        return ""
    for line in frontend_environment.read_text(encoding="utf-8").splitlines():
        if line.startswith("OCP_FRONTEND_MODULES="):
            return line.partition("=")[2].strip().strip('"').strip("'")
    return ""


def _migration_preflight(root: Path, enabled_ids: tuple[str, ...]) -> None:
    with _temporary_environment({"ENABLED_MODULES": ",".join(enabled_ids)}):
        get_settings.cache_clear()
        try:
            module_migrations.run(
                "preflight",
                install_root=root,
                enabled_module_ids=enabled_ids,
            )
        finally:
            get_settings.cache_clear()


def _frontend_preflight(environment: EnablementEnvironment) -> None:
    values = _environment_values(environment)
    subprocess.run(
        ["pnpm", "modules:check"],
        cwd=FRONTEND_ROOT,
        env={**os.environ, **values},
        check=True,
    )


def _frontend_package_preflight(
    installed_root: Path,
    excluded_builtin_modules: str = "",
) -> None:
    subprocess.run(
        ["pnpm", "modules:check"],
        cwd=FRONTEND_ROOT,
        env={
            **os.environ,
            "OCP_FRONTEND_MODULES": "",
            "OCP_BACKEND_MODULES": "",
            "OCP_INSTALLED_FRONTEND_MODULE_ROOTS": str(installed_root),
            "OCP_EXCLUDED_BUILTIN_MODULES": excluded_builtin_modules,
        },
        check=True,
    )


def _environment_values(environment: EnablementEnvironment) -> dict[str, str]:
    return {
        "ENABLED_MODULES": environment.enabled_modules,
        "OCP_FRONTEND_MODULES": environment.frontend_modules,
        "OCP_BACKEND_MODULES": environment.enabled_modules,
        "OCP_ENABLED_INSTALLED_BACKEND_PATHS": environment.runtime_backend_paths,
        "OCP_INSTALLED_FRONTEND_MODULE_ROOTS": (
            environment.installed_frontend_module_roots
        ),
        "OCP_EXCLUDED_BUILTIN_MODULES": environment.excluded_builtin_modules,
    }


@contextmanager
def _temporary_environment(values: Mapping[str, str]):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _render_table(installer: ModuleInstaller) -> str:
    inventory = installer.inventory()
    rows = ["ID\tVERSION\tKIND\tENABLED\tPUBLISHER\tBACKEND\tFRONTEND\tDIGEST"]
    rows.extend(
        "\t".join(
            (
                entry.id,
                entry.version,
                entry.kind,
                str(entry.enabled).lower(),
                entry.publisher or "-",
                str(entry.backend_present).lower(),
                str(entry.frontend_present).lower(),
                entry.digest or "-",
            )
        )
        for entry in inventory.modules
    )
    return "\n".join(rows)


@contextmanager
def _installer_package_input(path: Path):
    if path.suffix == ".ocp":
        with staged_ocp_bundle(path) as (package_root, _package):
            yield package_root
        return
    yield path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        help=f"Host-owned module root (default: ${INSTALL_ROOT_ENV} or {DEFAULT_INSTALL_ROOT}).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser("verify", help="Verify a local package input without changes.")
    verify.add_argument("package", type=Path)
    install = commands.add_parser("install", help="Install a verified package as disabled.")
    install.add_argument("package", type=Path)
    install_registry = commands.add_parser(
        "install-registry",
        help="Resolve and securely install an OCP bundle from Registry v1 as disabled.",
    )
    install_registry.add_argument("module_id")
    selection = install_registry.add_mutually_exclusive_group()
    selection.add_argument("--version", help="Install one exact semantic version.")
    selection.add_argument(
        "--channel",
        choices=("stable", "beta", "nightly"),
        help='Resolve a Registry channel (default: "stable").',
    )
    install_registry.add_argument(
        "--expected-sha256",
        help="Require this lowercase SHA-256 deployment pin.",
    )
    install_registry.add_argument(
        "--registry-url",
        help=(f"Registry base URL (default: ${REGISTRY_URL_ENV} or {DEFAULT_REGISTRY_URL})."),
    )
    enable = commands.add_parser("enable", help="Enable an installed module after preflight.")
    enable.add_argument("module_id")
    disable = commands.add_parser("disable", help="Disable an installed module without removal.")
    disable.add_argument("module_id")
    listing = commands.add_parser("list", help="List built-in and installed modules.")
    listing.add_argument("--format", choices=("json", "table"), default="json")
    environment = commands.add_parser(
        "env", help="Render deterministic deploy-time enablement from modules.lock."
    )
    environment.add_argument("--format", choices=("json", "shell"), default="shell")
    bundle = commands.add_parser("bundle", help="Build deterministic passive OCP bundles.")
    bundle_commands = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_build = bundle_commands.add_parser("build", help="Build one OCP v1 bundle.")
    bundle_build.add_argument("--manifest", type=Path, required=True)
    bundle_build.add_argument("--backend", type=Path)
    bundle_build.add_argument("--frontend", type=Path)
    bundle_build.add_argument("--publisher", required=True)
    bundle_build.add_argument("--source-reference", required=True)
    bundle_build.add_argument("--source-repository", required=True)
    bundle_build.add_argument("--source-commit", required=True)
    bundle_build.add_argument("--source-tag")
    bundle_build.add_argument("--build-workflow", required=True)
    bundle_build.add_argument("--license", required=True)
    bundle_build.add_argument("--sbom-reference")
    bundle_build.add_argument("--attestation-reference")
    bundle_build.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "bundle":
            digest = build_ocp_bundle(
                args.output,
                manifest=load_bundle_manifest(args.manifest),
                publisher=args.publisher,
                source=ModuleSource(
                    type="local",
                    reference=args.source_reference,
                ),
                provenance=ModuleProvenance(
                    source_repository=args.source_repository,
                    source_commit=args.source_commit,
                    source_tag=args.source_tag,
                    build_workflow=args.build_workflow,
                    license=args.license,
                    sbom_reference=args.sbom_reference,
                    attestation_reference=args.attestation_reference,
                ),
                backend_artifact=args.backend,
                frontend_artifact=args.frontend,
            )
            print(json.dumps({"bundle": str(args.output), "sha256": digest}, sort_keys=True))
            return 0

        installer = _installer(_install_root(args.root))
        if args.command == "verify":
            with _installer_package_input(args.package) as package_root:
                package = installer.verify_installable(package_root)
            print(package.model_dump_json(exclude={"manifest"}))
        elif args.command == "install":
            with _installer_package_input(args.package) as package_root:
                entry = installer.install(package_root)
            print(entry.model_dump_json())
            print("Module installed as disabled; enable and deploy it explicitly.")
        elif args.command == "install-registry":
            previous = next(
                (
                    item
                    for item in read_modules_lock(installer.lock_path).modules
                    if item.id == args.module_id
                ),
                None,
            )
            with _registry_client(args.registry_url) as registry:
                release = registry.resolve(
                    args.module_id,
                    version=args.version,
                    channel=args.channel,
                    expected_sha256=args.expected_sha256,
                )
                with (
                    registry.download(release) as downloaded,
                    staged_ocp_bundle(downloaded.path) as (package_root, package),
                ):
                    registry.validate_bundle(release, package)
                    entry = installer.install(package_root)
            print(
                json.dumps(
                    {
                        "module_id": release.module_id,
                        "version": release.version,
                        "channel": release.channel,
                        "sha256": downloaded.sha256,
                        "status": (
                            "already-installed"
                            if previous is not None
                            and previous.version == release.version
                            and previous.artifact.sha256 == release.sha256
                            else "installed"
                        ),
                        "enabled": entry.enabled,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            if entry.enabled:
                print("Module was already installed and remains enabled.")
            else:
                print("Module installed as disabled; enable and deploy it explicitly.")
        elif args.command == "enable":
            entry = installer.enable(args.module_id)
            print(entry.model_dump_json())
            print("Module enabled in modules.lock; build/deploy/restart is required.")
        elif args.command == "disable":
            entry = installer.disable(args.module_id)
            print(entry.model_dump_json())
            print("Module disabled in modules.lock; build/deploy/restart is required.")
        elif args.command == "list":
            print(
                installer.inventory().model_dump_json()
                if args.format == "json"
                else _render_table(installer)
            )
        elif args.command == "env":
            values = _environment_values(installer.enablement_environment())
            if args.format == "json":
                print(json.dumps(values, sort_keys=True, separators=(",", ":")))
            else:
                for key in sorted(values):
                    print(f"export {key}={shlex.quote(values[key])}")
    except (
        ModuleInstallerError,
        ModuleRegistryError,
        ValidationError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"modules: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

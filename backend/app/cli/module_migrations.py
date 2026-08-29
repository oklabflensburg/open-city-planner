"""Preflight und Ausführung des gemeinsamen Host-/Modul-Migrationsgraphen."""

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from alembic.config import Config

from app.core.config import BACKEND_ENV_FILE, get_settings
from app.platform.modules import (
    EntryPointModuleDiscovery,
    FirstPartyModuleDiscovery,
    scoped_module_python_paths,
)
from app.platform.modules.installer import (
    DEFAULT_INSTALL_ROOT,
    installed_backend_distribution_paths,
)
from app.platform.modules.migrations import MigrationCoordinator, MigrationStep
from app.platform.modules.persistence import (
    build_persistence_registry,
    resolve_available_persistence_definitions,
)
from app.platform.modules.runtime import resolve_module_definitions
from app.platform.modules.settings import (
    ModuleSettingsRegistry,
    build_module_settings_registry,
    read_module_environment,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
INSTALL_ROOT_ENV = "OCP_MODULE_INSTALL_ROOT"


def coordinator(
    *,
    installed_distribution_paths: Sequence[Path] | None = None,
    enabled_distribution_paths: Sequence[Path] | None = None,
) -> MigrationCoordinator:
    settings = get_settings()
    available_paths = tuple(
        installed_distribution_paths
        if installed_distribution_paths is not None
        else _installed_distribution_paths()
    )
    enabled_discovery_providers = (
        FirstPartyModuleDiscovery(
            excluded_module_ids=settings.excluded_builtin_module_list
        ),
        EntryPointModuleDiscovery(
            distribution_paths=enabled_distribution_paths
        )
        if enabled_distribution_paths is not None
        else EntryPointModuleDiscovery(),
    )
    enabled = resolve_module_definitions(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=enabled_discovery_providers,
        host_version=settings.api_version,
    )
    build_module_settings_registry(
        enabled,
        registry=ModuleSettingsRegistry(
            read_module_environment(env_file=BACKEND_ENV_FILE)
        ),
    )
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = settings.database_url
    available = resolve_available_persistence_definitions(
        (
            FirstPartyModuleDiscovery(
                excluded_module_ids=settings.excluded_builtin_module_list
            ),
            EntryPointModuleDiscovery(distribution_paths=available_paths),
        )
    )
    return MigrationCoordinator(config, build_persistence_registry(available))


def _install_root(value: Path | None = None) -> Path:
    return Path(value or os.environ.get(INSTALL_ROOT_ENV, DEFAULT_INSTALL_ROOT))


def _installed_distribution_paths(root: Path | None = None) -> tuple[Path, ...]:
    return installed_backend_distribution_paths(_install_root(root))


def run(
    action: str,
    revision: str | None = None,
    *,
    install_root: Path | None = None,
    enabled_module_ids: Sequence[str] | None = None,
) -> tuple[MigrationStep, ...] | None:
    all_installed_paths = _installed_distribution_paths(install_root)
    enabled_ids = frozenset(
        enabled_module_ids
        if enabled_module_ids is not None
        else get_settings().enabled_module_list
    )
    enabled_paths = tuple(
        path
        for path in all_installed_paths
        if path.parents[2].name in enabled_ids
    )
    with scoped_module_python_paths(all_installed_paths):
        active = coordinator(
            installed_distribution_paths=all_installed_paths,
            enabled_distribution_paths=enabled_paths,
        )
        if action == "preflight":
            return active.preflight()
        if action == "upgrade":
            return active.upgrade()
        if action == "downgrade":
            if not revision:
                raise ValueError("downgrade requires an explicit revision")
            active.downgrade(revision)
            return None
        raise ValueError(f'Unknown migration action "{action}".')


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or migrate the locally available host/module revision graph."
    )
    parser.add_argument("action", choices=("preflight", "upgrade", "downgrade"))
    parser.add_argument("revision", nargs="?", help="Explicit target for downgrade.")
    args = parser.parse_args()
    if args.action == "downgrade" and not args.revision:
        parser.error("downgrade requires an explicit revision")
    plan = run(args.action, args.revision)
    if plan is None:
        return 0
    for step in plan:
        print(f"{step.module_id}: {step.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

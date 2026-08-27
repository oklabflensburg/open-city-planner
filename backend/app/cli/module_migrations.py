"""Preflight und Ausführung des gemeinsamen Host-/Modul-Migrationsgraphen."""

import argparse
from pathlib import Path

from alembic.config import Config

from app.core.config import BACKEND_ENV_FILE, get_settings
from app.platform.modules import EntryPointModuleDiscovery, FirstPartyModuleDiscovery
from app.platform.modules.migrations import MigrationCoordinator
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


def coordinator() -> MigrationCoordinator:
    settings = get_settings()
    discovery_providers = (FirstPartyModuleDiscovery(), EntryPointModuleDiscovery())
    enabled = resolve_module_definitions(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=discovery_providers,
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
    available = resolve_available_persistence_definitions(discovery_providers)
    return MigrationCoordinator(config, build_persistence_registry(available))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or migrate the locally available host/module revision graph."
    )
    parser.add_argument("action", choices=("preflight", "upgrade", "downgrade"))
    parser.add_argument("revision", nargs="?", help="Explicit target for downgrade.")
    args = parser.parse_args()
    active = coordinator()
    if args.action == "preflight":
        plan = active.preflight()
    elif args.action == "upgrade":
        plan = active.upgrade()
    else:
        if not args.revision:
            parser.error("downgrade requires an explicit revision")
        active.downgrade(args.revision)
        return 0
    for step in plan:
        print(f"{step.module_id}: {step.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

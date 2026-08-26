"""Preflight und Ausführung des gemeinsamen Host-/Modul-Migrationsgraphen."""

import argparse
from pathlib import Path

from alembic.config import Config

from app.core.config import get_settings
from app.platform.modules import EntryPointModuleDiscovery, FirstPartyModuleDiscovery
from app.platform.modules.migrations import MigrationCoordinator
from app.platform.modules.persistence import build_persistence_registry
from app.platform.modules.runtime import resolve_module_definitions

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def coordinator() -> MigrationCoordinator:
    settings = get_settings()
    resolved = resolve_module_definitions(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=(FirstPartyModuleDiscovery(), EntryPointModuleDiscovery()),
        host_version=settings.api_version,
    )
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = settings.database_url
    return MigrationCoordinator(config, build_persistence_registry(resolved))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or migrate the enabled host/module revision graph."
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

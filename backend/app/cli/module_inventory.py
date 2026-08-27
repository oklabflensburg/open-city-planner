"""Generate the enabled backend module inventory from discovery and manifests."""

import argparse
from collections.abc import Sequence

from app.core.config import Settings, get_settings
from app.platform.modules import EntryPointModuleDiscovery, FirstPartyModuleDiscovery
from app.platform.modules.inventory import (
    BackendModuleInventory,
    OperationalModuleInventory,
    build_backend_module_inventory,
    build_operational_module_inventory,
)
from app.platform.modules.runtime import resolve_module_definitions


def resolve_backend_module_inventory(settings: Settings) -> BackendModuleInventory:
    """Resolve exactly the modules enabled for the backend runtime."""

    resolved = resolve_module_definitions(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=(FirstPartyModuleDiscovery(), EntryPointModuleDiscovery()),
        host_version=settings.api_version,
    )
    return build_backend_module_inventory(resolved)


def resolve_operational_module_inventory(settings: Settings) -> OperationalModuleInventory:
    """Resolve non-secret trust, provenance and capability status for administrators."""

    resolved = resolve_module_definitions(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=(FirstPartyModuleDiscovery(), EntryPointModuleDiscovery()),
        host_version=settings.api_version,
    )
    return build_operational_module_inventory(resolved)


def render_inventory(
    inventory: BackendModuleInventory | OperationalModuleInventory,
    output_format: str,
) -> str:
    if output_format == "json":
        return inventory.model_dump_json()
    if output_format == "env":
        if not isinstance(inventory, BackendModuleInventory):
            raise ValueError("The operational inventory has no frontend environment format.")
        return inventory.as_env()
    if output_format == "status-json":
        return inventory.model_dump_json()
    raise ValueError(f"Unsupported inventory format: {output_format}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("json", "env", "status-json"),
        default="json",
        help="Output JSON (stable contract) or the frontend environment transport.",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    inventory = (
        resolve_operational_module_inventory(settings)
        if args.format == "status-json"
        else resolve_backend_module_inventory(settings)
    )
    print(render_inventory(inventory, args.format))


if __name__ == "__main__":
    main()

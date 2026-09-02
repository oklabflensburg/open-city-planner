import json

from app.cli.module_inventory import render_inventory, resolve_backend_module_inventory
from app.core.config import Settings
from app.modules.reference.module import MANIFEST as REFERENCE_MANIFEST
from app.platform.modules.discovery import FirstPartyModuleDiscovery
from app.platform.modules.inventory import BackendModuleInventory


def inventory_for(enabled_modules: str) -> BackendModuleInventory:
    return resolve_backend_module_inventory(Settings(enabled_modules=enabled_modules))


def test_enabled_module_inventory_uses_discovered_manifest_version() -> None:
    inventory = inventory_for("reference")

    assert inventory.model_dump(mode="json") == {
        "modules": [
            {
                "id": REFERENCE_MANIFEST.id,
                "version": REFERENCE_MANIFEST.version,
            }
        ]
    }
    assert render_inventory(inventory, "env") == (
        f"{REFERENCE_MANIFEST.id}@{REFERENCE_MANIFEST.version}"
    )


def test_disabled_modules_produce_an_empty_inventory() -> None:
    inventory = inventory_for("")

    assert json.loads(render_inventory(inventory, "json")) == {"modules": []}
    assert render_inventory(inventory, "env") == ""


def test_removed_builtin_is_not_discoverable() -> None:
    discovered_ids = {
        definition.manifest.id
        for definition in FirstPartyModuleDiscovery().discover_available()
    }

    assert "analysis-areas" not in discovered_ids


def test_manual_frontend_inventory_cannot_override_backend_activation(monkeypatch) -> None:
    monkeypatch.setenv("OCP_BACKEND_MODULES", "analysis-areas@999.0.0")

    assert inventory_for("").modules == ()

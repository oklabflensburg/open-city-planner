import json

from app.cli.module_inventory import (
    render_inventory,
    resolve_backend_module_inventory,
    resolve_operational_module_inventory,
)
from app.core.config import Settings
from app.modules.analysis_areas.module import MANIFEST as ANALYSIS_AREAS_MANIFEST
from app.platform.modules.inventory import BackendModuleInventory


def inventory_for(enabled_modules: str) -> BackendModuleInventory:
    return resolve_backend_module_inventory(Settings(enabled_modules=enabled_modules))


def test_enabled_module_inventory_uses_discovered_manifest_version() -> None:
    inventory = inventory_for("analysis-areas")

    assert inventory.model_dump(mode="json") == {
        "modules": [
            {
                "id": ANALYSIS_AREAS_MANIFEST.id,
                "version": ANALYSIS_AREAS_MANIFEST.version,
            }
        ]
    }
    assert render_inventory(inventory, "env") == (
        f"{ANALYSIS_AREAS_MANIFEST.id}@{ANALYSIS_AREAS_MANIFEST.version}"
    )


def test_disabled_modules_produce_an_empty_inventory() -> None:
    inventory = inventory_for("")

    assert json.loads(render_inventory(inventory, "json")) == {"modules": []}
    assert render_inventory(inventory, "env") == ""


def test_inventory_preserves_deterministic_resolved_module_order() -> None:
    inventory = inventory_for("reference,analysis-areas")

    assert [module.id for module in inventory.modules] == ["analysis-areas", "reference"]


def test_manual_frontend_inventory_cannot_override_backend_activation(monkeypatch) -> None:
    monkeypatch.setenv("OCP_BACKEND_MODULES", "analysis-areas@999.0.0")

    assert inventory_for("").modules == ()


def test_operational_inventory_adds_host_trust_and_capabilities_without_changing_env() -> None:
    settings = Settings(enabled_modules="analysis-areas")
    compatibility = resolve_backend_module_inventory(settings)
    operational = resolve_operational_module_inventory(settings)

    assert compatibility.model_dump(mode="json") == {
        "modules": [{"id": "analysis-areas", "version": "1.0.0"}]
    }
    assert operational.model_dump(mode="json") == {
        "modules": [
            {
                "id": "analysis-areas",
                "version": "1.0.0",
                "trust_class": "first-party",
                "capabilities": [
                    "analysis-areas.public-api",
                    "analysis-areas.lookup",
                    "analysis-areas.geojson",
                ],
                "source": "https://github.com/oklabflensburg/open-city-planner",
                "package": "open-city-map-backend",
                "package_version": "0.1.0",
                "commit": None,
                "integrity": None,
            }
        ]
    }
    assert render_inventory(compatibility, "env") == "analysis-areas@1.0.0"
    assert '"trust_class":"first-party"' in render_inventory(operational, "status-json")

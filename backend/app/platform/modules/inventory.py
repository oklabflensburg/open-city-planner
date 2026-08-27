"""Public technical inventory derived from resolved backend module manifests."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.platform.modules.manifest import ModuleId, ModuleManifestV1, SemanticVersion
from app.platform.modules.sdk import ModuleDefinition


class BackendModuleInventoryEntry(BaseModel):
    """Public compatibility metadata for one enabled backend module."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: ModuleId
    version: SemanticVersion


class BackendModuleInventory(BaseModel):
    """Stable machine-readable contract for enabled backend modules."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    modules: tuple[BackendModuleInventoryEntry, ...]

    def as_env(self) -> str:
        """Render the compatibility transport consumed by the frontend host."""

        return ",".join(f"{module.id}@{module.version}" for module in self.modules)


def build_backend_module_inventory(
    resolved_definitions: Sequence[tuple[ModuleDefinition, ModuleManifestV1]],
) -> BackendModuleInventory:
    """Project resolved manifests into their public ID/version inventory."""

    return BackendModuleInventory(
        modules=tuple(
            BackendModuleInventoryEntry(id=manifest.id, version=manifest.version)
            for _, manifest in resolved_definitions
        )
    )


__all__ = [
    "BackendModuleInventory",
    "BackendModuleInventoryEntry",
    "build_backend_module_inventory",
]

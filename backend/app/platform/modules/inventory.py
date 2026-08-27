"""Public technical inventory derived from resolved backend module manifests."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from app.platform.modules.manifest import ModuleId, ModuleManifestV1, SemanticVersion
from app.platform.modules.trust import ModuleTrustClass, TrustedModuleDefinition


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
    resolved_definitions: Sequence[tuple[TrustedModuleDefinition, ModuleManifestV1]],
) -> BackendModuleInventory:
    """Project resolved manifests into their public ID/version inventory."""

    return BackendModuleInventory(
        modules=tuple(
            BackendModuleInventoryEntry(id=manifest.id, version=manifest.version)
            for _, manifest in resolved_definitions
        )
    )


class OperationalModuleInventoryEntry(BaseModel):
    """Non-secret status and provenance for administration and audit."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: ModuleId
    version: SemanticVersion
    trust_class: ModuleTrustClass
    capabilities: tuple[str, ...]
    source: str
    package: str | None = None
    package_version: str | None = None
    commit: str | None = None
    integrity: str | None = None


class OperationalModuleInventory(BaseModel):
    """Operational view kept separate from the frontend compatibility contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    modules: tuple[OperationalModuleInventoryEntry, ...]


def build_operational_module_inventory(
    resolved_definitions: Sequence[tuple[TrustedModuleDefinition, ModuleManifestV1]],
) -> OperationalModuleInventory:
    """Project host-authorized trust and manifest capabilities without secrets."""

    return OperationalModuleInventory(
        modules=tuple(
            OperationalModuleInventoryEntry(
                id=manifest.id,
                version=manifest.version,
                trust_class=definition.trust.trust_class,
                capabilities=tuple(manifest.capabilities),
                source=definition.trust.source,
                package=definition.trust.package,
                package_version=definition.trust.package_version,
                commit=definition.trust.commit,
                integrity=definition.trust.integrity,
            )
            for definition, manifest in resolved_definitions
        )
    )


__all__ = [
    "BackendModuleInventory",
    "BackendModuleInventoryEntry",
    "OperationalModuleInventory",
    "OperationalModuleInventoryEntry",
    "build_backend_module_inventory",
    "build_operational_module_inventory",
]

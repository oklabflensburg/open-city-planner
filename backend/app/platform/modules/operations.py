"""Read-only operational projection of the active backend module runtime."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.platform.modules.manifest import (
    ModuleId,
    NamespacedId,
    SemanticVersion,
    SemanticVersionRange,
)

type ModuleRuntimeStatus = Literal["loaded", "registered", "running"]
type SafeModuleOrigin = Literal["built-in", "entry-point", "unknown"]


class OperationalStatusModel(BaseModel):
    """Strict immutable base for host-owned operational response models."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ModuleOperationalDependencyStatus(OperationalStatusModel):
    """One already validated dependency resolved in the active runtime."""

    id: ModuleId
    requirement: SemanticVersionRange
    resolved: SemanticVersion
    optional: bool
    compatible: Literal[True] = True


class ModuleOperationalStatus(OperationalStatusModel):
    """Small, safe projection of one active module record."""

    id: ModuleId
    version: SemanticVersion
    status: ModuleRuntimeStatus
    enabled: Literal[True] = True
    registered: bool
    capabilities: tuple[NamespacedId, ...]
    dependencies: tuple[ModuleOperationalDependencyStatus, ...]
    origin: SafeModuleOrigin
    job_count: int = Field(ge=0)


class ModuleOperationalStatusResponse(OperationalStatusModel):
    """Administrative operational snapshot for all active runtime records."""

    modules: tuple[ModuleOperationalStatus, ...]


def safe_module_origin(origin: str) -> SafeModuleOrigin:
    """Reduce internal import/entry-point details to a bounded public category."""

    if origin.startswith("app.modules."):
        return "built-in"
    if origin.startswith("entry-point:"):
        return "entry-point"
    return "unknown"


__all__ = [
    "ModuleOperationalDependencyStatus",
    "ModuleOperationalStatus",
    "ModuleOperationalStatusResponse",
    "ModuleRuntimeStatus",
    "SafeModuleOrigin",
    "safe_module_origin",
]

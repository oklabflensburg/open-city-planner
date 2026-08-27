"""Host-owned trust grants for installed in-process modules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.sdk import ModuleDefinition

_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256_INTEGRITY = re.compile(r"^sha256:[0-9a-f]{64}$")


class ModuleTrustClass(StrEnum):
    """Trust classes that may authorize code inside the host process."""

    FIRST_PARTY = "first-party"
    REVIEWED_COMMUNITY = "reviewed-community"


@dataclass(frozen=True, slots=True)
class ModuleTrustGrant:
    """Deployment-owned authorization for one installed module source."""

    module_id: str
    trust_class: ModuleTrustClass
    source: str
    module_version: str | None = None
    package: str | None = None
    package_version: str | None = None
    commit: str | None = None
    integrity: str | None = None
    license: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None

    def __post_init__(self) -> None:
        if not self.module_id or not self.source:
            raise ValueError("Module trust grants require a module ID and source.")
        parsed_source = urlsplit(self.source)
        if parsed_source.scheme != "https" or not parsed_source.netloc:
            raise ValueError("Module trust sources must use an absolute HTTPS URL.")
        if parsed_source.username or parsed_source.password or parsed_source.fragment:
            raise ValueError("Module trust sources cannot contain credentials or fragments.")
        if self.trust_class is ModuleTrustClass.FIRST_PARTY:
            return
        required_strings = {
            "module_version": self.module_version,
            "package": self.package,
            "package_version": self.package_version,
            "commit": self.commit,
            "integrity": self.integrity,
            "license": self.license,
            "reviewed_by": self.reviewed_by,
        }
        missing = [name for name, value in required_strings.items() if not value]
        if self.reviewed_at is None:
            missing.append("reviewed_at")
        if missing:
            raise ValueError(
                "Reviewed community trust grants require " + ", ".join(sorted(missing)) + "."
            )
        if not _COMMIT_SHA.fullmatch(self.commit or ""):
            raise ValueError("Reviewed community commits must be full lowercase Git SHAs.")
        if not _SHA256_INTEGRITY.fullmatch(self.integrity or ""):
            raise ValueError("Reviewed community integrity must use sha256:<64 lowercase hex>.")
        assert self.reviewed_at is not None
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("Reviewed timestamps must include a timezone.")


@dataclass(frozen=True, slots=True)
class TrustedModuleDefinition:
    """A passive definition paired with a decision made by its discovery host."""

    definition: ModuleDefinition
    trust: ModuleTrustGrant

    @property
    def manifest(self):
        return self.definition.manifest

    @property
    def loader(self):
        return self.definition.loader

    @property
    def origin(self) -> str:
        return self.definition.origin

    @property
    def declared_id(self) -> str:
        return self.definition.declared_id

    @property
    def persistence(self):
        return self.definition.persistence

    @property
    def settings(self):
        return self.definition.settings


def first_party_definition(
    definition: ModuleDefinition,
    *,
    source: str = "https://github.com/oklabflensburg/open-city-planner",
) -> TrustedModuleDefinition:
    """Authorize a definition through a host-controlled first-party catalog."""

    return TrustedModuleDefinition(
        definition=definition,
        trust=ModuleTrustGrant(
            module_id=definition.declared_id,
            trust_class=ModuleTrustClass.FIRST_PARTY,
            source=source,
        ),
    )


def validate_trust_binding(
    definition: TrustedModuleDefinition,
    manifest: ModuleManifestV1,
) -> None:
    """Bind host authorization to the immutable manifest identity and version."""

    trust = definition.trust
    if trust.module_id != manifest.id:
        raise ValueError("The host trust grant does not match the manifest module ID.")
    if (
        trust.trust_class is ModuleTrustClass.REVIEWED_COMMUNITY
        and trust.module_version != manifest.version
    ):
        raise ValueError("The reviewed module version does not match the manifest version.")


__all__ = [
    "ModuleTrustClass",
    "ModuleTrustGrant",
    "TrustedModuleDefinition",
    "first_party_definition",
    "validate_trust_binding",
]

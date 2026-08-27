"""Kontrollierte First-Party- und Python-Entry-Point-Discovery."""

from collections.abc import Callable, Mapping, Sequence
from importlib import metadata
from types import MappingProxyType

from app.platform.modules.errors import ModuleDiscoveryError
from app.platform.modules.sdk import ModuleDefinition
from app.platform.modules.trust import (
    ModuleTrustClass,
    ModuleTrustGrant,
    TrustedModuleDefinition,
    first_party_definition,
)

ENTRY_POINT_GROUP = "open_city_planner.modules"
type DefinitionSource = ModuleDefinition | Callable[[], ModuleDefinition]

# First-Party-Module werden hier später deklarativ ergänzt. Leer bedeutet, dass die
# produktive Legacy-Anwendung ohne neue Module unverändert startet.
FIRST_PARTY_MODULES: Mapping[str, DefinitionSource] = MappingProxyType({})
FIRST_PARTY_ENTRY_POINTS: Mapping[str, str] = MappingProxyType(
    {
        "analysis-areas": "open-city-map-backend",
        "reference": "open-city-map-backend",
    }
)
FIRST_PARTY_SOURCE = "https://github.com/oklabflensburg/open-city-planner"


class FirstPartyModuleDiscovery:
    """Discovery aus einem fachneutralen, deploy-time kontrollierten Katalog."""

    def __init__(self, catalog: Mapping[str, DefinitionSource] = FIRST_PARTY_MODULES) -> None:
        self._catalog = catalog

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[TrustedModuleDefinition]:
        definitions: list[TrustedModuleDefinition] = []
        for module_id in sorted(enabled_module_ids.intersection(self._catalog)):
            source = self._catalog[module_id]
            try:
                definition = source() if callable(source) else source
            except Exception as exc:
                raise ModuleDiscoveryError(
                    "The first-party module definition could not be loaded.",
                    module_id=module_id,
                    origin="first-party",
                ) from exc
            if not isinstance(definition, ModuleDefinition):
                raise ModuleDiscoveryError(
                    "The first-party catalog entry is not a ModuleDefinition.",
                    module_id=module_id,
                    origin="first-party",
                )
            definitions.append(
                first_party_definition(
                    ModuleDefinition(
                        manifest=definition.manifest,
                        loader=definition.loader,
                        origin=definition.origin,
                        declared_id=module_id,
                        persistence=definition.persistence,
                        settings=definition.settings,
                    )
                )
            )
        return tuple(definitions)


class EntryPointModuleDiscovery:
    """Discovery host-authorized installed Python distributions."""

    def __init__(
        self,
        reviewed_installs: Mapping[str, ModuleTrustGrant] | None = None,
    ) -> None:
        self._reviewed_installs = reviewed_installs or {}

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[TrustedModuleDefinition]:
        definitions: list[TrustedModuleDefinition] = []
        entry_points = metadata.entry_points().select(group=ENTRY_POINT_GROUP)
        for entry_point in sorted(entry_points, key=lambda candidate: candidate.name):
            if entry_point.name not in enabled_module_ids:
                continue
            origin = f"entry-point:{entry_point.name}={entry_point.value}"
            distribution = getattr(entry_point, "dist", None)
            distribution_name = getattr(distribution, "name", None)
            distribution_version = getattr(distribution, "version", None)
            expected_first_party_distribution = FIRST_PARTY_ENTRY_POINTS.get(entry_point.name)
            if expected_first_party_distribution is not None:
                if distribution_name != expected_first_party_distribution:
                    raise ModuleDiscoveryError(
                        "The first-party entry point is not provided by the host distribution.",
                        module_id=entry_point.name,
                        origin=origin,
                    )
                trust = ModuleTrustGrant(
                    module_id=entry_point.name,
                    trust_class=ModuleTrustClass.FIRST_PARTY,
                    source=FIRST_PARTY_SOURCE,
                    package=distribution_name,
                    package_version=distribution_version,
                )
            else:
                trust = self._reviewed_installs.get(entry_point.name)
                if trust is None or trust.trust_class is not ModuleTrustClass.REVIEWED_COMMUNITY:
                    raise ModuleDiscoveryError(
                        "The enabled community entry point has no reviewed host trust grant.",
                        module_id=entry_point.name,
                        origin=origin,
                    )
                if (
                    trust.package != distribution_name
                    or trust.package_version != distribution_version
                ):
                    raise ModuleDiscoveryError(
                        "The installed community distribution does not match its reviewed trust grant.",
                        module_id=entry_point.name,
                        origin=origin,
                    )
            try:
                definition = entry_point.load()
            except Exception as exc:
                raise ModuleDiscoveryError(
                    "The enabled Python entry point could not be loaded.",
                    module_id=entry_point.name,
                    origin=origin,
                ) from exc
            if not isinstance(definition, ModuleDefinition):
                raise ModuleDiscoveryError(
                    "The Python entry point does not expose a ModuleDefinition.",
                    module_id=entry_point.name,
                    origin=origin,
                )
            definitions.append(
                TrustedModuleDefinition(
                    definition=ModuleDefinition(
                        manifest=definition.manifest,
                        loader=definition.loader,
                        origin=origin,
                        declared_id=entry_point.name,
                        persistence=definition.persistence,
                        settings=definition.settings,
                    ),
                    trust=trust,
                )
            )
        return tuple(definitions)

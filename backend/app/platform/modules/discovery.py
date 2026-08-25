"""Kontrollierte First-Party- und Python-Entry-Point-Discovery."""

from collections.abc import Callable, Mapping, Sequence
from importlib import metadata
from types import MappingProxyType

from app.platform.modules.contracts import ModuleDefinition
from app.platform.modules.errors import ModuleDiscoveryError

ENTRY_POINT_GROUP = "open_city_planner.modules"
type DefinitionSource = ModuleDefinition | Callable[[], ModuleDefinition]

# First-Party-Module werden hier später deklarativ ergänzt. Leer bedeutet, dass die
# produktive Legacy-Anwendung ohne neue Module unverändert startet.
FIRST_PARTY_MODULES: Mapping[str, DefinitionSource] = MappingProxyType({})


class FirstPartyModuleDiscovery:
    """Discovery aus einem fachneutralen, deploy-time kontrollierten Katalog."""

    def __init__(self, catalog: Mapping[str, DefinitionSource] = FIRST_PARTY_MODULES) -> None:
        self._catalog = catalog

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        definitions: list[ModuleDefinition] = []
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
                ModuleDefinition(
                    manifest=definition.manifest,
                    loader=definition.loader,
                    origin=definition.origin,
                    declared_id=module_id,
                )
            )
        return tuple(definitions)


class EntryPointModuleDiscovery:
    """Discovery vertrauenswürdiger installierter Python-Distributionen."""

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        definitions: list[ModuleDefinition] = []
        entry_points = metadata.entry_points().select(group=ENTRY_POINT_GROUP)
        for entry_point in sorted(entry_points, key=lambda candidate: candidate.name):
            if entry_point.name not in enabled_module_ids:
                continue
            origin = f"entry-point:{entry_point.name}={entry_point.value}"
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
                ModuleDefinition(
                    manifest=definition.manifest,
                    loader=definition.loader,
                    origin=origin,
                    declared_id=entry_point.name,
                )
            )
        return tuple(definitions)

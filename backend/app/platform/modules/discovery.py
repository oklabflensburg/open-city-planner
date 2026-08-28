"""Kontrollierte First-Party- und Python-Entry-Point-Discovery."""

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import import_module, metadata
from pathlib import Path

from app.platform.modules.errors import ModuleDiscoveryError
from app.platform.modules.sdk import ModuleDefinition

ENTRY_POINT_GROUP = "open_city_planner.modules"
ENABLED_INSTALLED_BACKEND_PATHS_ENV = "OCP_ENABLED_INSTALLED_BACKEND_PATHS"
type DefinitionSource = ModuleDefinition | Callable[[], ModuleDefinition]

BUILTIN_MODULES_DIRECTORY = Path(__file__).resolve().parents[2] / "modules"


class FirstPartyModuleDiscovery:
    """Discovery aus Built-in-Konvention oder explizitem Test-/Composition-Katalog."""

    def __init__(self, catalog: Mapping[str, DefinitionSource] | None = None) -> None:
        self._catalog = catalog

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        return self._discover(enabled_module_ids)

    def discover_available(self) -> Sequence[ModuleDefinition]:
        """Entdecke alle lokal vorhandenen Built-ins ohne sie runtime-seitig zu aktivieren."""

        module_ids = (
            frozenset(_available_builtin_module_ids())
            if self._catalog is None
            else frozenset(self._catalog)
        )
        return self._discover(module_ids)

    def _discover(self, module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        definitions: list[ModuleDefinition] = []
        selected_ids = (
            module_ids if self._catalog is None else module_ids.intersection(self._catalog)
        )
        for module_id in sorted(selected_ids):
            try:
                definition = (
                    _load_builtin_definition(module_id)
                    if self._catalog is None
                    else _resolve_source(self._catalog[module_id])
                )
            except Exception as exc:
                raise ModuleDiscoveryError(
                    "The first-party module definition could not be loaded.",
                    module_id=module_id,
                    origin="first-party",
                ) from exc
            if definition is None:
                continue
            if not isinstance(definition, ModuleDefinition):
                raise ModuleDiscoveryError(
                    "The first-party module does not expose a ModuleDefinition.",
                    module_id=module_id,
                    origin="first-party",
                )
            definitions.append(
                ModuleDefinition(
                    manifest=definition.manifest,
                    loader=definition.loader,
                    origin=definition.origin,
                    declared_id=module_id,
                    persistence=definition.persistence,
                    settings=definition.settings,
                )
            )
        return tuple(definitions)


def _load_builtin_definition(module_id: str) -> ModuleDefinition | None:
    """Load an enabled repository module by the built-in directory convention."""

    python_name = module_id.replace("-", "_")
    if not (BUILTIN_MODULES_DIRECTORY / python_name / "module.py").is_file():
        return None
    module = import_module(f"app.modules.{python_name}.module")
    return module.DEFINITION


def _available_builtin_module_ids() -> tuple[str, ...]:
    """Leite Built-in-IDs generisch aus lokalen Python-Modulpaketen ab."""

    if not BUILTIN_MODULES_DIRECTORY.is_dir():
        return ()
    return tuple(
        sorted(
            path.name.replace("_", "-")
            for path in BUILTIN_MODULES_DIRECTORY.iterdir()
            if path.is_dir()
            and path.name.isidentifier()
            and (path / "module.py").is_file()
        )
    )


def _resolve_source(source: DefinitionSource) -> ModuleDefinition:
    return source() if callable(source) else source


class EntryPointModuleDiscovery:
    """Discovery vertrauenswürdiger installierter Python-Distributionen."""

    def __init__(self, distribution_paths: Sequence[Path] | None = None) -> None:
        configured = distribution_paths
        if configured is None:
            configured = tuple(
                Path(value)
                for value in os.environ.get(
                    ENABLED_INSTALLED_BACKEND_PATHS_ENV, ""
                ).split(os.pathsep)
                if value
            )
        self._distribution_paths = tuple(path.resolve() for path in configured)

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        return self._discover(enabled_module_ids)

    def discover_available(self) -> Sequence[ModuleDefinition]:
        """Passive Definitionen aller lokal installierten Modul-Entry-Points ermitteln."""

        return self._discover(None)

    def _discover(
        self, enabled_module_ids: frozenset[str] | None
    ) -> Sequence[ModuleDefinition]:
        definitions: list[ModuleDefinition] = []
        entry_points = _module_entry_points(self._distribution_paths)
        for located in sorted(
            entry_points,
            key=lambda candidate: (
                candidate.entry_point.name,
                candidate.entry_point.value,
                "" if candidate.distribution_path is None else str(candidate.distribution_path),
            ),
        ):
            entry_point = located.entry_point
            if (
                enabled_module_ids is not None
                and entry_point.name not in enabled_module_ids
            ):
                continue
            origin = f"entry-point:{entry_point.name}={entry_point.value}"
            try:
                with scoped_module_python_paths(
                    ()
                    if located.distribution_path is None
                    else (located.distribution_path,)
                ):
                    definition = entry_point.load()
            except Exception as exc:
                raise ModuleDiscoveryError(
                    "The installed Python entry point definition could not be loaded.",
                    module_id=entry_point.name,
                    origin=origin,
                ) from exc
            if not isinstance(definition, ModuleDefinition):
                raise ModuleDiscoveryError(
                    "The installed Python entry point does not expose a ModuleDefinition.",
                    module_id=entry_point.name,
                    origin=origin,
                )
            definitions.append(
                ModuleDefinition(
                    manifest=definition.manifest,
                    loader=_scoped_loader(
                        definition.loader,
                        located.distribution_path,
                    ),
                    origin=origin,
                    declared_id=entry_point.name,
                    persistence=definition.persistence,
                    settings=definition.settings,
                )
            )
        return tuple(definitions)


@dataclass(frozen=True, slots=True)
class _LocatedEntryPoint:
    entry_point: metadata.EntryPoint
    distribution_path: Path | None


def _module_entry_points(
    distribution_paths: Sequence[Path],
) -> tuple[_LocatedEntryPoint, ...]:
    """Find host and explicitly installed module entry points without path mutation."""

    located: list[_LocatedEntryPoint] = [
        _LocatedEntryPoint(entry_point, _distribution_root(entry_point))
        for entry_point in metadata.entry_points().select(group=ENTRY_POINT_GROUP)
    ]
    for distribution_path in distribution_paths:
        for distribution in metadata.distributions(path=[str(distribution_path)]):
            located.extend(
                _LocatedEntryPoint(entry_point, distribution_path)
                for entry_point in distribution.entry_points
                if entry_point.group == ENTRY_POINT_GROUP
            )

    unique: dict[tuple[str, str, str], _LocatedEntryPoint] = {}
    for candidate in located:
        key = (
            candidate.entry_point.name,
            candidate.entry_point.value,
            ""
            if candidate.distribution_path is None
            else str(candidate.distribution_path.resolve()),
        )
        unique.setdefault(key, candidate)
    return tuple(unique.values())


def _distribution_root(entry_point: metadata.EntryPoint) -> Path | None:
    distribution = getattr(entry_point, "dist", None)
    if distribution is None:
        return None
    try:
        return Path(distribution.locate_file("")).resolve()
    except (AttributeError, OSError, TypeError):
        return None


def _scoped_loader(
    loader: Callable[[], object],
    distribution_path: Path | None,
) -> Callable[[], object]:
    if distribution_path is None:
        return loader

    def load() -> object:
        with scoped_module_python_paths((distribution_path,)):
            return loader()

    return load


@contextmanager
def scoped_module_python_paths(paths: Sequence[Path]):
    """Temporarily append module paths and restore the exact process path afterwards."""

    previous = sys.path.copy()
    try:
        for path in paths:
            value = str(path.resolve())
            if value not in sys.path:
                sys.path.append(value)
        yield
    finally:
        sys.path[:] = previous


def activate_enabled_module_python_paths(
    paths: Sequence[Path] | None = None,
) -> tuple[Path, ...]:
    """Append only enabled installed package roots for one runtime process."""

    configured = paths
    if configured is None:
        configured = tuple(
            Path(value)
            for value in os.environ.get(
                ENABLED_INSTALLED_BACKEND_PATHS_ENV, ""
            ).split(os.pathsep)
            if value
        )
    resolved = tuple(path.resolve() for path in configured)
    for path in resolved:
        value = str(path)
        if value not in sys.path:
            sys.path.append(value)
    return resolved

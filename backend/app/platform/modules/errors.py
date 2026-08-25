"""Strukturierte Fehler des Modulmanifest-Contracts."""

from collections.abc import Sequence
from typing import Any


class ModuleManifestError(ValueError):
    """Basisklasse für ungültige Manifestdaten."""

    def __init__(
        self,
        message: str,
        *,
        module_id: str | None = None,
        origin: str | None = None,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.module_id = module_id
        self.origin = origin
        self.details = details or []


class UnsupportedManifestVersionError(ModuleManifestError):
    """Die angegebene Manifest-Schemaversion wird nicht unterstützt."""

    def __init__(self, manifest_version: object, *, origin: str | None = None) -> None:
        super().__init__(
            f"Unsupported module manifest version: {manifest_version!r}; supported version is 1.",
            origin=origin,
        )
        self.manifest_version = manifest_version


class InvalidRuntimeVersionError(ModuleManifestError):
    """Host oder SDK haben keine gültige SemVer-Version übergeben."""

    def __init__(self, target: str, version: str) -> None:
        super().__init__(f"Current {target} version {version!r} is not valid SemVer.")
        self.target = target
        self.version = version


class DuplicateModuleIdError(ModuleManifestError):
    """Mehrere verfügbare Manifeste verwenden dieselbe Modul-ID."""

    def __init__(
        self,
        module_id: str,
        *,
        origins: Sequence[str | None] = (),
    ) -> None:
        known_origins = [origin for origin in origins if origin]
        origin_suffix = f" Origins: {', '.join(known_origins)}." if known_origins else ""
        super().__init__(
            f'Duplicate module ID "{module_id}".{origin_suffix}',
            module_id=module_id,
        )
        self.origins = tuple(origins)


class DuplicateConfigNamespaceError(ModuleManifestError):
    """Zwei Module beanspruchen denselben Konfigurations-Namespace."""

    def __init__(self, namespace: str, module_ids: Sequence[str]) -> None:
        joined_ids = ", ".join(module_ids)
        super().__init__(
            f'Config namespace "{namespace}" is used by multiple modules: {joined_ids}.'
        )
        self.namespace = namespace
        self.module_ids = tuple(module_ids)


class ModuleCompatibilityError(ModuleManifestError):
    """Ein Modul ist mit der aktuellen Host- oder SDK-Version inkompatibel."""

    def __init__(
        self,
        module_id: str,
        module_version: str,
        target: str,
        expected: str,
        found: str,
    ) -> None:
        super().__init__(
            f'Module "{module_id}" {module_version} requires {target} {expected}, '
            f"current {target} is {found}.",
            module_id=module_id,
        )
        self.module_version = module_version
        self.target = target
        self.expected = expected
        self.found = found


class ModuleDependencyError(ModuleManifestError):
    """Basisklasse für ungültige Modulabhängigkeiten."""


class MissingModuleDependencyError(ModuleDependencyError):
    """Eine erforderliche Modulabhängigkeit ist nicht verfügbar."""

    def __init__(self, module_id: str, dependency_id: str, expected: str) -> None:
        super().__init__(
            f'Module "{module_id}" requires module "{dependency_id}" {expected}, '
            "but it is not available.",
            module_id=module_id,
        )
        self.dependency_id = dependency_id
        self.expected = expected


class ModuleDependencyVersionError(ModuleDependencyError):
    """Eine vorhandene required/optional Dependency hat die falsche Version."""

    def __init__(
        self,
        module_id: str,
        dependency_id: str,
        expected: str,
        found: str,
        *,
        optional: bool,
    ) -> None:
        dependency_kind = "optional module" if optional else "module"
        super().__init__(
            f'Module "{module_id}" requires {dependency_kind} "{dependency_id}" '
            f"{expected}, found {found}.",
            module_id=module_id,
        )
        self.dependency_id = dependency_id
        self.expected = expected
        self.found = found
        self.optional = optional


class ModuleSelfDependencyError(ModuleDependencyError):
    """Ein Modul darf weder required noch optional von sich selbst abhängen."""

    def __init__(self, module_id: str, *, optional: bool) -> None:
        dependency_kind = "optional" if optional else "required"
        super().__init__(
            f'Module "{module_id}" has a {dependency_kind} dependency on itself.',
            module_id=module_id,
        )
        self.optional = optional


class ModuleDependencyCycleError(ModuleDependencyError):
    """Der Modulgraph enthält einen Zyklus."""

    def __init__(self, cycle: Sequence[str]) -> None:
        cycle_path = tuple(cycle)
        super().__init__(f"Module dependency cycle detected: {' -> '.join(cycle_path)}.")
        self.cycle = cycle_path


class ModuleRuntimeError(RuntimeError):
    """Basisklasse für Fehler während einer Phase der Module Runtime."""

    def __init__(
        self,
        message: str,
        *,
        phase: str,
        module_id: str | None = None,
        origin: str | None = None,
    ) -> None:
        context = [f"phase={phase}"]
        if module_id is not None:
            context.append(f"module_id={module_id}")
        if origin is not None:
            context.append(f"origin={origin}")
        super().__init__(f"Module runtime error ({', '.join(context)}): {message}")
        self.phase = phase
        self.module_id = module_id
        self.origin = origin


class ModuleDiscoveryError(ModuleRuntimeError):
    """Discovery eines aktivierten Moduls ist fehlgeschlagen."""

    def __init__(
        self, message: str, *, module_id: str | None = None, origin: str | None = None
    ) -> None:
        super().__init__(message, phase="discovery", module_id=module_id, origin=origin)


class ModuleValidationError(ModuleRuntimeError):
    """Ein entdecktes Modul konnte nicht validiert werden."""

    def __init__(
        self, message: str, *, module_id: str | None = None, origin: str | None = None
    ) -> None:
        super().__init__(message, phase="validation", module_id=module_id, origin=origin)


class ModuleLoadError(ModuleRuntimeError):
    """Die Instanziierung eines validierten Moduls ist fehlgeschlagen."""

    def __init__(self, message: str, *, module_id: str, origin: str | None = None) -> None:
        super().__init__(message, phase="import", module_id=module_id, origin=origin)


class ModuleRegistrationError(ModuleRuntimeError):
    """Die deklarative Registrierung eines Moduls ist fehlgeschlagen."""

    def __init__(
        self, message: str, *, module_id: str | None = None, origin: str | None = None
    ) -> None:
        super().__init__(message, phase="registration", module_id=module_id, origin=origin)


class ModuleStartupError(ModuleRuntimeError):
    """Ein Modul konnte nicht vollständig gestartet werden."""

    def __init__(self, message: str, *, module_id: str | None = None) -> None:
        super().__init__(message, phase="startup", module_id=module_id)


class ModuleShutdownError(ModuleRuntimeError):
    """Mindestens ein Modul konnte nicht sauber beendet werden."""

    def __init__(self, message: str, *, module_id: str | None = None) -> None:
        super().__init__(message, phase="shutdown", module_id=module_id)

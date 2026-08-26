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


class DuplicatePersistenceSchemaError(ModuleManifestError):
    """Zwei Module beanspruchen dasselbe PostgreSQL-Schema."""

    def __init__(self, schema: str, module_ids: Sequence[str]) -> None:
        joined_ids = ", ".join(module_ids)
        super().__init__(
            f'Persistence schema "{schema}" is owned by multiple modules: {joined_ids}.'
        )
        self.schema = schema
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


class ModulePersistenceError(RuntimeError):
    """Ein passiver Persistence-Beitrag verletzt den Ownership-Contract."""

    def __init__(
        self,
        message: str,
        *,
        module_id: str | None = None,
        schema: str | None = None,
        phase: str = "preflight",
    ) -> None:
        context = [f"phase={phase}"]
        if module_id is not None:
            context.append(f"module_id={module_id}")
        if schema is not None:
            context.append(f"schema={schema}")
        super().__init__(f"Module persistence error ({', '.join(context)}): {message}")
        self.module_id = module_id
        self.schema = schema
        self.phase = phase


class ServiceRegistryError(RuntimeError):
    """Basisklasse für verletzte Cross-Module-Service-Verträge."""

    def __init__(
        self,
        message: str,
        *,
        service_id: str | None = None,
        requested_version: int | None = None,
        provider_module: str | None = None,
        consumer_module: str | None = None,
        available_versions: Sequence[int] = (),
        available_services: Sequence[str] = (),
    ) -> None:
        context: list[str] = []
        if service_id is not None:
            context.append(f"service_id={service_id}")
        if requested_version is not None:
            context.append(f"requested_version={requested_version}")
        if provider_module is not None:
            context.append(f"provider_module={provider_module}")
        if consumer_module is not None:
            context.append(f"consumer_module={consumer_module}")
        if available_versions:
            context.append(
                "available_versions=" + ",".join(str(version) for version in available_versions)
            )
        if available_services:
            context.append("available_services=" + ",".join(available_services))
        suffix = f" ({', '.join(context)})" if context else ""
        super().__init__(f"Service registry error{suffix}: {message}")
        self.service_id = service_id
        self.requested_version = requested_version
        self.provider_module = provider_module
        self.consumer_module = consumer_module
        self.available_versions = tuple(available_versions)
        self.available_services = tuple(available_services)


class DuplicateServiceRegistrationError(ServiceRegistryError):
    """Dieselbe Service-ID und Version wurde mehr als einmal registriert."""


class MissingRequiredServiceError(ServiceRegistryError):
    """Ein erforderlicher öffentlicher Service ist nicht registriert."""


class IncompatibleServiceVersionError(ServiceRegistryError):
    """Eine Service-ID existiert, aber nicht in der angeforderten Version."""


class ServiceContractMismatchError(ServiceRegistryError):
    """Die Service-ID und Version sind an einen anderen Protocol-Typ gebunden."""


class UndeclaredServiceDependencyError(ServiceRegistryError):
    """Der Consumer hat den Service-Owner nicht passend im Manifest deklariert."""


class ServiceRegistrySealedError(ServiceRegistryError):
    """Nach Abschluss der Modulregistrierung sind Mutationen verboten."""


class ModuleSettingsError(RuntimeError):
    """Basisklasse für namespacete Modulkonfigurationsfehler ohne Werteausgabe."""

    def __init__(
        self,
        message: str,
        *,
        module_id: str | None = None,
        namespace: str | None = None,
        field_name: str | None = None,
        environment_key: str | None = None,
        error_type: str | None = None,
    ) -> None:
        context: list[str] = []
        if module_id is not None:
            context.append(f"module_id={module_id}")
        if namespace is not None:
            context.append(f"namespace={namespace}")
        if field_name is not None:
            context.append(f"field={field_name}")
        if environment_key is not None:
            context.append(f"environment_key={environment_key}")
        if error_type is not None:
            context.append(f"error_type={error_type}")
        suffix = f" ({', '.join(context)})" if context else ""
        super().__init__(f"Module settings error{suffix}: {message}")
        self.module_id = module_id
        self.namespace = namespace
        self.field_name = field_name
        self.environment_key = environment_key
        self.error_type = error_type


class ModuleSettingsValidationError(ModuleSettingsError):
    """Ein aktives Modul konnte seine Konfiguration nicht sicher validieren."""


class ModuleSettingsNamespaceError(ModuleSettingsError):
    """Manifest, Contribution oder Environment verletzen das Namespace-Ownership."""


class ModulePublicConfigError(ModuleSettingsError):
    """Ein als öffentlich markierter Wert ist nicht sicher exportierbar."""

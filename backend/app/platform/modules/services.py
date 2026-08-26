"""Runtime-skopierte Registry für öffentliche Cross-Module-Service-Contracts."""

import re
from dataclasses import dataclass
from typing import TypeVar, cast

from app.platform.modules.errors import (
    DuplicateServiceRegistrationError,
    IncompatibleServiceVersionError,
    MissingRequiredServiceError,
    ServiceContractMismatchError,
    ServiceRegistryError,
    ServiceRegistrySealedError,
    UndeclaredServiceDependencyError,
)
from app.platform.modules.manifest import ModuleManifestV1

T = TypeVar("T")
_SERVICE_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+$")


@dataclass(frozen=True, slots=True)
class RegisteredService:
    service_id: str
    version: int
    provider_module: str
    contract: type[object]
    implementation: object
    deprecated_since: str | None = None
    replacement: str | None = None


class ServiceRegistry:
    """Host-owned Registry mit exakten, parallel registrierbaren Integer-Versionen."""

    def __init__(self) -> None:
        self._services: dict[tuple[str, int], RegisteredService] = {}
        self._sealed = False

    @property
    def services(self) -> tuple[RegisteredService, ...]:
        return tuple(self._services[key] for key in sorted(self._services))

    @property
    def sealed(self) -> bool:
        return self._sealed

    def bind(self, manifest: ModuleManifestV1) -> "ModuleServiceRegistryAdapter":
        return ModuleServiceRegistryAdapter(self, manifest)

    def register(
        self,
        *,
        provider_module: str,
        contract: type[T],
        implementation: T,
        service_id: str,
        version: int,
        deprecated_since: str | None = None,
        replacement: str | None = None,
    ) -> None:
        owner = _validate_service_reference(service_id, version, contract)
        _validate_deprecation_metadata(
            service_id=service_id,
            version=version,
            deprecated_since=deprecated_since,
            replacement=replacement,
        )
        if implementation is None:
            raise ServiceRegistryError(
                "Service implementations must not be None.",
                service_id=service_id,
                requested_version=version,
                provider_module=provider_module,
            )
        if self._sealed:
            raise ServiceRegistrySealedError(
                "Service registration is closed.",
                service_id=service_id,
                requested_version=version,
                provider_module=provider_module,
            )
        if owner != provider_module:
            raise ServiceRegistryError(
                "Providers may register services only in their own module namespace.",
                service_id=service_id,
                requested_version=version,
                provider_module=provider_module,
            )
        key = (service_id, version)
        if key in self._services:
            registered = self._services[key]
            raise DuplicateServiceRegistrationError(
                "The service ID and version are already registered.",
                service_id=service_id,
                requested_version=version,
                provider_module=registered.provider_module,
            )
        self._services[key] = RegisteredService(
            service_id=service_id,
            version=version,
            provider_module=provider_module,
            contract=cast(type[object], contract),
            implementation=implementation,
            deprecated_since=deprecated_since,
            replacement=replacement,
        )

    def lookup(
        self,
        contract: type[T],
        *,
        service_id: str,
        version: int,
        consumer_module: str,
        required: bool,
    ) -> T | None:
        provider_module = _validate_service_reference(service_id, version, contract)
        registered = self._services.get((service_id, version))
        if registered is None:
            available_versions = self._available_versions(service_id)
            if available_versions:
                raise IncompatibleServiceVersionError(
                    "The requested exact service version is not registered.",
                    service_id=service_id,
                    requested_version=version,
                    provider_module=provider_module,
                    consumer_module=consumer_module,
                    available_versions=available_versions,
                    available_services=self._available_service_references(),
                )
            if required:
                raise MissingRequiredServiceError(
                    "The required service is not registered.",
                    service_id=service_id,
                    requested_version=version,
                    provider_module=provider_module,
                    consumer_module=consumer_module,
                    available_services=self._available_service_references(),
                )
            return None
        if registered.contract is not contract:
            raise ServiceContractMismatchError(
                "The registered service uses a different public contract type.",
                service_id=service_id,
                requested_version=version,
                provider_module=registered.provider_module,
                consumer_module=consumer_module,
            )
        return cast(T, registered.implementation)

    def resolve_unique(self, contract: type[T], *, consumer_module: str) -> RegisteredService:
        matches = [service for service in self._services.values() if service.contract is contract]
        if len(matches) != 1:
            raise MissingRequiredServiceError(
                "Compatibility resolve() requires exactly one registered contract; "
                "use require() with an explicit service ID and version.",
                consumer_module=consumer_module,
                available_services=self._available_service_references(),
            )
        return matches[0]

    def seal(self) -> None:
        self._sealed = True

    def _available_versions(self, service_id: str) -> tuple[int, ...]:
        return tuple(
            sorted(version for candidate, version in self._services if candidate == service_id)
        )

    def _available_service_references(self) -> tuple[str, ...]:
        return tuple(f"{service_id}@{version}" for service_id, version in sorted(self._services))


class ModuleServiceRegistryAdapter:
    """An genau ein Provider-/Consumer-Modul gebundener öffentlicher SDK-Adapter."""

    def __init__(self, registry: ServiceRegistry, manifest: ModuleManifestV1) -> None:
        self._registry = registry
        self._manifest = manifest

    def register(
        self,
        contract: type[T],
        implementation: T,
        *,
        service_id: str,
        version: int,
        deprecated_since: str | None = None,
        replacement: str | None = None,
    ) -> None:
        self._registry.register(
            provider_module=self._manifest.id,
            contract=contract,
            implementation=implementation,
            service_id=service_id,
            version=version,
            deprecated_since=deprecated_since,
            replacement=replacement,
        )

    def require(self, contract: type[T], *, service_id: str, version: int) -> T:
        self._validate_dependency(service_id, required=True)
        service = self._registry.lookup(
            contract,
            service_id=service_id,
            version=version,
            consumer_module=self._manifest.id,
            required=True,
        )
        assert service is not None
        return service

    def optional(self, contract: type[T], *, service_id: str, version: int) -> T | None:
        self._validate_dependency(service_id, required=False)
        return self._registry.lookup(
            contract,
            service_id=service_id,
            version=version,
            consumer_module=self._manifest.id,
            required=False,
        )

    def resolve(self, contract: type[T]) -> T:
        registered = self._registry.resolve_unique(contract, consumer_module=self._manifest.id)
        self._validate_dependency(registered.service_id, required=True)
        return cast(T, registered.implementation)

    def _validate_dependency(self, service_id: str, *, required: bool) -> None:
        provider_module = service_id.partition(".")[0]
        if provider_module == self._manifest.id:
            return
        declared_required = provider_module in self._manifest.requires.modules
        declared_optional = provider_module in self._manifest.optional.modules
        if declared_required or (not required and declared_optional):
            return
        kind = "required" if required else "required or optional"
        raise UndeclaredServiceDependencyError(
            f"The provider must be declared as a {kind} module dependency.",
            service_id=service_id,
            provider_module=provider_module,
            consumer_module=self._manifest.id,
        )


def _validate_service_reference(service_id: str, version: int, contract: type[object]) -> str:
    if not isinstance(service_id, str) or not _SERVICE_ID.fullmatch(service_id):
        raise ServiceRegistryError(
            "Service IDs must use the form <owner-module>.<service-name>.",
            service_id=service_id if isinstance(service_id, str) else None,
        )
    if len(service_id) > 160:
        raise ServiceRegistryError(
            "Service IDs must not exceed 160 characters.", service_id=service_id
        )
    if type(version) is not int or version < 1:
        raise ServiceRegistryError(
            "Service versions must be positive integers.",
            service_id=service_id,
        )
    if not isinstance(contract, type):
        raise ServiceRegistryError(
            "Service contracts must be public Protocol or class types.",
            service_id=service_id,
            requested_version=version,
        )
    return service_id.partition(".")[0]


def _validate_deprecation_metadata(
    *,
    service_id: str,
    version: int,
    deprecated_since: str | None,
    replacement: str | None,
) -> None:
    if deprecated_since is not None and (
        not isinstance(deprecated_since, str)
        or not deprecated_since.strip()
        or len(deprecated_since) > 128
    ):
        raise ServiceRegistryError(
            "deprecated_since must be a non-empty value of at most 128 characters.",
            service_id=service_id,
            requested_version=version,
        )
    if replacement is None:
        return
    if deprecated_since is None:
        raise ServiceRegistryError(
            "A replacement requires deprecated_since metadata.",
            service_id=service_id,
            requested_version=version,
        )
    if not isinstance(replacement, str) or not _SERVICE_ID.fullmatch(replacement):
        raise ServiceRegistryError(
            "Replacement service IDs must use the form <owner-module>.<service-name>.",
            service_id=service_id,
            requested_version=version,
        )
    if len(replacement) > 160 or replacement.partition(".")[0] != service_id.partition(".")[0]:
        raise ServiceRegistryError(
            "Replacement services must remain in the same owner namespace and ID length limit.",
            service_id=service_id,
            requested_version=version,
        )


__all__ = ["ModuleServiceRegistryAdapter", "RegisteredService", "ServiceRegistry"]

"""Deterministische Backend-Module-Registry und Lifecycle-Orchestrierung."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import FastAPI

from app.platform.modules.context import ModuleContextFactory
from app.platform.modules.contracts import (
    LifecycleContribution,
    ModuleDiscoveryProvider,
    ModuleRegistrationContext,
)
from app.platform.modules.dependency_graph import resolve_module_order
from app.platform.modules.errors import (
    ModuleDiscoveryError,
    ModuleLoadError,
    ModuleManifestError,
    ModuleRegistrationError,
    ModuleShutdownError,
    ModuleStartupError,
    ModuleValidationError,
)
from app.platform.modules.manifest import ModuleManifestV1, parse_manifest, validate_manifests
from app.platform.modules.sdk import BackendModule, ModuleContext, ModuleDefinition
from app.platform.modules.services import ServiceRegistry
from app.platform.modules.settings import (
    ModuleSettingsRegistry,
    build_module_settings_registry,
)

logger = logging.getLogger(__name__)
MODULE_SDK_VERSION = "1.4.0"


@dataclass(slots=True)
class ModuleRecord:
    """Kompakter interner Runtime-Eintrag ohne vollständige Lifecycle-State-Machine."""

    manifest: ModuleManifestV1
    module: BackendModule
    origin: str
    load_index: int
    context: ModuleContext
    registration: ModuleRegistrationContext
    registered: bool = False

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(self.manifest.capabilities)


class ModuleRegistry:
    """Hält validierte Module in ihrer deterministischen Load Order."""

    def __init__(self, records: Sequence[ModuleRecord] = ()) -> None:
        self._records = list(records)

    @property
    def records(self) -> tuple[ModuleRecord, ...]:
        return tuple(self._records)

    def get(self, module_id: str) -> ModuleRecord:
        for record in self._records:
            if record.manifest.id == module_id:
                return record
        raise KeyError(module_id)

    def capabilities(self, module_id: str) -> tuple[str, ...]:
        return self.get(module_id).capabilities


class ModuleRuntime:
    """Registriert Router und orchestriert asynchrone Module-Lifecycles."""

    def __init__(
        self,
        registry: ModuleRegistry,
        *,
        service_registry: ServiceRegistry | None = None,
        settings_registry: ModuleSettingsRegistry | None = None,
    ) -> None:
        self.registry = registry
        self._service_registry = service_registry
        self._settings_registry = settings_registry
        self._attached_app: FastAPI | None = None
        self._started: list[tuple[ModuleRecord, LifecycleContribution]] = []
        self._running = False

    @property
    def module_ids(self) -> tuple[str, ...]:
        return tuple(record.manifest.id for record in self.registry.records)

    @property
    def public_module_config(self) -> dict[str, dict[str, object]]:
        if self._settings_registry is None:
            return {}
        return self._settings_registry.public_config

    def register(self, app: FastAPI) -> None:
        """Deklariere Beiträge einmalig und binde Router kontrolliert an den Host."""

        if self._attached_app is not None:
            raise ModuleRegistrationError("The module runtime is already attached to an app.")

        for record in self.registry.records:
            fields = _log_fields(record, "registration")
            logger.info("Module registration started", extra=fields)
            try:
                record.module.register(record.context)
                record.registration.close()
            except Exception as exc:
                record.registration.close()
                raise ModuleRegistrationError(
                    "The module register() hook failed.",
                    module_id=record.manifest.id,
                    origin=record.origin,
                ) from exc
            record.registered = True
            logger.info("Module registration completed", extra=fields)

        if self._service_registry is not None:
            self._service_registry.seal()

        for record in self.registry.records:
            for contribution in record.registration.routers:
                try:
                    app.include_router(
                        contribution.router,
                        prefix=contribution.prefix,
                        tags=list(contribution.tags) or None,
                    )
                except Exception as exc:
                    raise ModuleRegistrationError(
                        "A module router could not be attached to the host.",
                        module_id=record.manifest.id,
                        origin=record.origin,
                    ) from exc
        self._attached_app = app

    async def startup(self) -> None:
        """Starte Beiträge in Load Order und räume Teilstarts bei Fehlern auf."""

        if self._attached_app is None:
            raise ModuleStartupError("The module runtime is not attached to an app.")
        if self._running:
            raise ModuleStartupError("The module runtime has already been started.")

        for record in self.registry.records:
            for contribution in record.registration.lifecycle:
                try:
                    if contribution.startup is not None:
                        await contribution.startup()
                    self._started.append((record, contribution))
                except Exception as exc:
                    await self._cleanup_after_startup_failure()
                    raise ModuleStartupError(
                        "A module startup hook failed.", module_id=record.manifest.id
                    ) from exc
        self._running = True

    async def shutdown(self) -> None:
        """Beende gestartete Beiträge vollständig in umgekehrter Load Order."""

        first_failure: tuple[ModuleRecord, Exception] | None = None
        while self._started:
            record, contribution = self._started.pop()
            if contribution.shutdown is None:
                continue
            try:
                await contribution.shutdown()
            except Exception as exc:
                if first_failure is None:
                    first_failure = (record, exc)
                logger.exception("Module shutdown failed", extra=_log_fields(record, "shutdown"))
        self._running = False
        if first_failure is not None:
            record, exc = first_failure
            raise ModuleShutdownError(
                "A module shutdown hook failed.", module_id=record.manifest.id
            ) from exc

    async def _cleanup_after_startup_failure(self) -> None:
        while self._started:
            record, contribution = self._started.pop()
            if contribution.shutdown is None:
                continue
            try:
                await contribution.shutdown()
            except Exception:
                logger.exception(
                    "Module cleanup after startup failure failed",
                    extra=_log_fields(record, "shutdown"),
                )


def create_module_runtime(
    *,
    enabled_module_ids: Sequence[str],
    discovery_providers: Sequence[ModuleDiscoveryProvider],
    host_version: str,
    sdk_version: str = MODULE_SDK_VERSION,
    context_factory: ModuleContextFactory | None = None,
) -> ModuleRuntime:
    """Discover, validiere, sortiere und instanziiere aktivierte Module fail-fast."""

    resolved = resolve_module_definitions(
        enabled_module_ids=enabled_module_ids,
        discovery_providers=discovery_providers,
        host_version=host_version,
        sdk_version=sdk_version,
    )
    definitions_by_id = {manifest.id: definition for definition, manifest in resolved}
    ordered = tuple(manifest for _, manifest in resolved)

    records: list[ModuleRecord] = []
    active_context_factory = context_factory or ModuleContextFactory()
    if active_context_factory.settings_registry is not None:
        build_module_settings_registry(
            resolved,
            registry=active_context_factory.settings_registry,
        )
    for load_index, manifest in enumerate(ordered):
        definition = definitions_by_id[manifest.id]
        try:
            module = definition.loader()
            if module.manifest != manifest:
                raise ValueError("loaded module manifest does not match its validated definition")
            register = module.register
            if not callable(register):
                raise TypeError("loaded module has no callable register hook")
        except Exception as exc:
            raise ModuleLoadError(
                "The validated module could not be instantiated.",
                module_id=manifest.id,
                origin=definition.origin,
            ) from exc
        registration = ModuleRegistrationContext()
        records.append(
            ModuleRecord(
                manifest=manifest,
                module=module,
                origin=definition.origin,
                load_index=load_index,
                context=active_context_factory.create(manifest, registration),
                registration=registration,
            )
        )
    return ModuleRuntime(
        ModuleRegistry(records),
        service_registry=active_context_factory.service_registry,
        settings_registry=active_context_factory.settings_registry,
    )


def resolve_module_definitions(
    *,
    enabled_module_ids: Sequence[str],
    discovery_providers: Sequence[ModuleDiscoveryProvider],
    host_version: str,
    sdk_version: str = MODULE_SDK_VERSION,
) -> tuple[tuple[ModuleDefinition, ModuleManifestV1], ...]:
    """Entdecke und ordne passive Definitionen, ohne Modul-Runtimecode zu laden."""

    enabled = frozenset(enabled_module_ids)
    definitions: list[ModuleDefinition] = []
    for provider in discovery_providers:
        try:
            definitions.extend(
                definition
                for definition in provider.discover(enabled)
                if definition.declared_id in enabled
            )
        except ModuleDiscoveryError:
            raise
        except Exception as exc:
            raise ModuleDiscoveryError(
                f"Discovery provider {type(provider).__name__} failed."
            ) from exc

    parsed: list[tuple[ModuleDefinition, ModuleManifestV1]] = []
    for definition in definitions:
        try:
            manifest = (
                definition.manifest
                if isinstance(definition.manifest, ModuleManifestV1)
                else parse_manifest(definition.manifest, origin=definition.origin)
            )
            if definition.declared_id != manifest.id:
                raise ModuleValidationError(
                    "The discovery ID does not match the manifest ID.",
                    module_id=definition.declared_id,
                    origin=definition.origin,
                )
        except ModuleValidationError:
            raise
        except ModuleManifestError as exc:
            raise ModuleValidationError(
                str(exc), module_id=exc.module_id, origin=definition.origin
            ) from exc
        parsed.append((definition, manifest))

    discovered_ids = {manifest.id for _, manifest in parsed}
    missing_ids = sorted(enabled.difference(discovered_ids))
    if missing_ids:
        module_id = missing_ids[0]
        raise ModuleDiscoveryError(
            "The enabled module was not found in a configured discovery source.",
            module_id=module_id,
        )

    manifests = [manifest for _, manifest in parsed]
    origins = [definition.origin for definition, _ in parsed]
    try:
        validated = validate_manifests(
            manifests,
            host_version=host_version,
            sdk_version=sdk_version,
            origins=origins,
        )
        ordered = resolve_module_order(validated)
    except ModuleManifestError as exc:
        origin = exc.origin
        if origin is None and exc.module_id is not None:
            origin = next(
                (
                    definition.origin
                    for definition, manifest in parsed
                    if manifest.id == exc.module_id
                ),
                None,
            )
        raise ModuleValidationError(str(exc), module_id=exc.module_id, origin=origin) from exc

    definitions_by_id = {manifest.id: definition for definition, manifest in parsed}
    return tuple((definitions_by_id[manifest.id], manifest) for manifest in ordered)


def _log_fields(record: ModuleRecord, phase: str) -> dict[str, str]:
    return {
        "module_id": record.manifest.id,
        "module_version": record.manifest.version,
        "module_phase": phase,
    }

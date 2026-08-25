"""Kleine öffentliche Registrierungsverträge der Backend-Module-Runtime."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

from app.platform.modules.manifest import ManifestInput, ModuleManifestV1

type ModuleLifecycleHook = Callable[[], Awaitable[None]]
type ModuleLoader = Callable[[], "BackendModule"]


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    """Passive Discovery-Metadaten und verzögerte Modulinstanziierung."""

    manifest: ManifestInput | ModuleManifestV1
    loader: ModuleLoader
    origin: str
    declared_id: str


@dataclass(frozen=True, slots=True)
class RouterContribution:
    """Vom Host kontrolliert einzubindender FastAPI-Router."""

    router: APIRouter
    prefix: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LifecycleContribution:
    """Zusammengehörige asynchrone Startup-/Shutdown-Beiträge."""

    startup: ModuleLifecycleHook | None = None
    shutdown: ModuleLifecycleHook | None = None


class ModuleRegistrationContext:
    """Minimaler Context für Router und asynchrone Lifecycle-Beiträge."""

    def __init__(self) -> None:
        self._routers: list[RouterContribution] = []
        self._lifecycle: list[LifecycleContribution] = []
        self._open = True

    @property
    def routers(self) -> Sequence[RouterContribution]:
        return tuple(self._routers)

    @property
    def lifecycle(self) -> Sequence[LifecycleContribution]:
        return tuple(self._lifecycle)

    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = "",
        tags: Sequence[str] = (),
    ) -> None:
        self._ensure_open()
        self._routers.append(RouterContribution(router, prefix, tuple(tags)))

    def add_lifecycle(
        self,
        *,
        startup: ModuleLifecycleHook | None = None,
        shutdown: ModuleLifecycleHook | None = None,
    ) -> None:
        self._ensure_open()
        if startup is None and shutdown is None:
            raise ValueError("A lifecycle contribution requires a startup or shutdown hook.")
        self._lifecycle.append(LifecycleContribution(startup, shutdown))

    def close(self) -> None:
        self._open = False

    def _ensure_open(self) -> None:
        if not self._open:
            raise RuntimeError("The module registration context is closed.")


class BackendModule(Protocol):
    """Öffentlicher, bewusst kleiner Backend-Modulvertrag."""

    manifest: ModuleManifestV1

    def register(self, context: ModuleRegistrationContext) -> None: ...


class ModuleDiscoveryProvider(Protocol):
    """Liefert nur Definitionen explizit aktivierter deploy-time Module."""

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]: ...

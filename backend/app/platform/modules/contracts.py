"""Hostseitige Beitragsobjekte und #94-Kompatibilität der Module-Runtime."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

from app.platform.modules.sdk import (
    BackendModule,
    ModuleDefinition,
    ModuleLifecycleHook,
)


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


class ModuleDiscoveryProvider(Protocol):
    """Liefert nur Definitionen explizit aktivierter deploy-time Module."""

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]: ...


__all__ = [
    "BackendModule",
    "LifecycleContribution",
    "ModuleDefinition",
    "ModuleDiscoveryProvider",
    "ModuleLifecycleHook",
    "ModuleRegistrationContext",
    "RouterContribution",
]

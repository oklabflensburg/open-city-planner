"""Reine, deterministische Auflösung des Modulabhängigkeitsgraphen."""

import heapq
from collections.abc import Sequence

from app.platform.modules.errors import (
    DuplicateModuleIdError,
    MissingModuleDependencyError,
    ModuleDependencyCycleError,
    ModuleSelfDependencyError,
)
from app.platform.modules.manifest import ModuleManifestV1


def _available_dependencies(
    manifest: ModuleManifestV1,
    modules_by_id: dict[str, ModuleManifestV1],
) -> set[str]:
    dependencies = set(manifest.requires.modules)
    dependencies.update(
        dependency_id
        for dependency_id in manifest.optional.modules
        if dependency_id in modules_by_id
    )
    return dependencies


def _find_cycle(
    modules_by_id: dict[str, ModuleManifestV1],
) -> tuple[str, ...]:
    state: dict[str, int] = {module_id: 0 for module_id in modules_by_id}
    stack: list[str] = []
    stack_positions: dict[str, int] = {}

    def visit(module_id: str) -> tuple[str, ...] | None:
        state[module_id] = 1
        stack_positions[module_id] = len(stack)
        stack.append(module_id)
        dependencies = _available_dependencies(modules_by_id[module_id], modules_by_id)
        for dependency_id in sorted(dependencies):
            if state[dependency_id] == 0:
                cycle = visit(dependency_id)
                if cycle is not None:
                    return cycle
            elif state[dependency_id] == 1:
                start = stack_positions[dependency_id]
                return tuple(stack[start:] + [dependency_id])
        stack.pop()
        stack_positions.pop(module_id)
        state[module_id] = 2
        return None

    for module_id in sorted(modules_by_id):
        if state[module_id] == 0:
            cycle = visit(module_id)
            if cycle is not None:
                return cycle
    return ()


def resolve_module_order(manifests: Sequence[ModuleManifestV1]) -> tuple[ModuleManifestV1, ...]:
    """Sortiere Dependencies vor Consumer; gleiche Kandidaten lexikografisch nach ID."""

    modules_by_id: dict[str, ModuleManifestV1] = {}
    for manifest in manifests:
        if manifest.id in modules_by_id:
            raise DuplicateModuleIdError(manifest.id)
        modules_by_id[manifest.id] = manifest

    dependents: dict[str, set[str]] = {module_id: set() for module_id in modules_by_id}
    indegree: dict[str, int] = {module_id: 0 for module_id in modules_by_id}
    for manifest in manifests:
        dependencies = _available_dependencies(manifest, modules_by_id)
        for dependency_id in sorted(dependencies):
            if dependency_id == manifest.id:
                raise ModuleSelfDependencyError(
                    manifest.id,
                    optional=dependency_id in manifest.optional.modules,
                )
            if dependency_id not in modules_by_id:
                expected = manifest.requires.modules[dependency_id]
                raise MissingModuleDependencyError(manifest.id, dependency_id, expected)
            dependents[dependency_id].add(manifest.id)
            indegree[manifest.id] += 1

    ready = [module_id for module_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[ModuleManifestV1] = []
    while ready:
        module_id = heapq.heappop(ready)
        order.append(modules_by_id[module_id])
        for dependent_id in sorted(dependents[module_id]):
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                heapq.heappush(ready, dependent_id)

    if len(order) != len(manifests):
        raise ModuleDependencyCycleError(_find_cycle(modules_by_id))
    return tuple(order)

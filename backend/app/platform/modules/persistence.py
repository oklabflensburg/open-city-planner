"""Hostseitige Ownership-Registry für Legacy- und Modul-Persistence."""

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import Base
from app.db.session import AsyncSessionLocal
from app.platform.modules.errors import ModulePersistenceError
from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.sdk import (
    ModuleDefinition,
    ModuleMigrationSource,
    ModulePersistenceContribution,
)

logger = logging.getLogger(__name__)


class HostDatabaseSessionProvider:
    """Öffnet eine Host-Session mit genau einer Commit-/Rollback-Grenze."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session, session.begin():
            yield session


@dataclass(frozen=True, slots=True)
class RegisteredPersistence:
    module_id: str
    metadata: MetaData
    schema: str | None
    migration_source: ModuleMigrationSource | None
    adopted_tables: frozenset[str] = frozenset()
    legacy: bool = False


class LegacyPersistenceProvider:
    """Kontrollierter Strangler-Adapter für das bestehende zentrale Base.metadata."""

    module_id = "host-legacy"

    def contribution(self) -> RegisteredPersistence:
        # Der Paketimport ist die einzige kontrollierte Legacy-Modellliste. Alembic
        # selbst muss dadurch keine Fachmodelle mehr einzeln kennen.
        import app.models  # noqa: F401

        return RegisteredPersistence(
            module_id=self.module_id,
            metadata=Base.metadata,
            schema=None,
            migration_source=None,
            legacy=True,
        )


class PersistenceRegistry:
    """Aggregiert Metadata und Migration Sources in validierter Modulreihenfolge."""

    def __init__(self) -> None:
        self._legacy: RegisteredPersistence | None = None
        self._modules: dict[str, RegisteredPersistence] = {}
        self._schema_owners: dict[str, str] = {}
        self._adopted_table_owners: dict[str, str] = {}
        self._module_order: tuple[str, ...] = ()

    def register_legacy(self, provider: LegacyPersistenceProvider) -> None:
        if self._legacy is not None:
            raise ModulePersistenceError("Legacy persistence is already registered.")
        self._legacy = provider.contribution()

    def register(
        self,
        manifest: ModuleManifestV1,
        contribution: ModulePersistenceContribution,
    ) -> None:
        module_id = manifest.id
        persistence = manifest.persistence
        if module_id in self._modules:
            raise ModulePersistenceError(
                "Persistence is already registered for this module.", module_id=module_id
            )
        if persistence is None:
            raise ModulePersistenceError(
                "The module manifest does not declare persistence.", module_id=module_id
            )
        if contribution.module_id != module_id:
            raise ModulePersistenceError(
                "The contribution module ID does not match the manifest.", module_id=module_id
            )
        if contribution.schema != persistence.schema_name:
            raise ModulePersistenceError(
                "The contribution schema does not match the manifest.",
                module_id=module_id,
                schema=contribution.schema,
            )
        owner = self._schema_owners.get(contribution.schema)
        if owner is not None:
            raise ModulePersistenceError(
                f'The schema is already owned by module "{owner}".',
                module_id=module_id,
                schema=contribution.schema,
            )
        if persistence.migrations != (contribution.migration_source is not None):
            expectation = "requires" if persistence.migrations else "forbids"
            raise ModulePersistenceError(
                f"The manifest {expectation} a migration source.", module_id=module_id
            )
        expected_namespace = revision_namespace_for(module_id)
        if (
            contribution.migration_source is not None
            and contribution.migration_source.revision_namespace != expected_namespace
        ):
            raise ModulePersistenceError(
                f'Revision namespace must be "{expected_namespace}".', module_id=module_id
            )
        foreign_tables = sorted(
            table.fullname
            for table in contribution.metadata.tables.values()
            if table.schema != contribution.schema
            and not (
                table.schema is None
                and table.name in contribution.adopted_tables
            )
        )
        if foreign_tables:
            raise ModulePersistenceError(
                "Module metadata contains tables outside its owned schema: "
                + ", ".join(foreign_tables),
                module_id=module_id,
                schema=contribution.schema,
            )
        unqualified_tables = {
            table.name
            for table in contribution.metadata.tables.values()
            if table.schema is None
        }
        if contribution.adopted_tables != unqualified_tables:
            raise ModulePersistenceError(
                "Adopted tables must exactly match the contribution's unqualified metadata tables.",
                module_id=module_id,
                schema=contribution.schema,
            )
        if contribution.adopted_tables and any(
            table.schema == contribution.schema
            for table in contribution.metadata.tables.values()
        ):
            raise ModulePersistenceError(
                "Adopted-table metadata cannot be combined with new schema-owned tables.",
                module_id=module_id,
                schema=contribution.schema,
            )
        for table_name in sorted(contribution.adopted_tables):
            table_owner = self._adopted_table_owners.get(table_name)
            if table_owner is not None:
                raise ModulePersistenceError(
                    f'The adopted table is already owned by module "{table_owner}".',
                    module_id=module_id,
                )
        self._schema_owners[contribution.schema] = module_id
        self._adopted_table_owners.update(
            {table_name: module_id for table_name in contribution.adopted_tables}
        )
        self._modules[module_id] = RegisteredPersistence(
            module_id=module_id,
            metadata=contribution.metadata,
            schema=contribution.schema,
            migration_source=contribution.migration_source,
            adopted_tables=contribution.adopted_tables,
        )

    def seal(self, ordered_manifests: Sequence[ModuleManifestV1]) -> None:
        order = tuple(manifest.id for manifest in ordered_manifests)
        missing = sorted(set(self._modules).difference(order))
        if missing:
            raise ModulePersistenceError(
                "Registered persistence is absent from the resolved module order: "
                + ", ".join(missing)
            )
        self._module_order = order

    @property
    def contributions(self) -> tuple[RegisteredPersistence, ...]:
        result: list[RegisteredPersistence] = []
        if self._legacy is not None:
            result.append(self._legacy)
        result.extend(
            self._modules[module_id]
            for module_id in self._module_order
            if module_id in self._modules
        )
        return tuple(result)

    @property
    def target_metadata(self) -> tuple[MetaData, ...]:
        return tuple(
            contribution.metadata
            for contribution in self.contributions
            if not contribution.adopted_tables
        )

    @property
    def owned_schemas(self) -> frozenset[str]:
        return frozenset(self._schema_owners)

    @property
    def migration_sources(self) -> tuple[tuple[str, ModuleMigrationSource], ...]:
        return tuple(
            (contribution.module_id, contribution.migration_source)
            for contribution in self.contributions
            if contribution.migration_source is not None
        )


def revision_namespace_for(module_id: str) -> str:
    return f"mod_{module_id.replace('-', '_')}"


def build_persistence_registry(
    resolved_definitions: Sequence[tuple[ModuleDefinition, ModuleManifestV1]],
    *,
    include_legacy: bool = True,
) -> PersistenceRegistry:
    registry = PersistenceRegistry()
    if include_legacy:
        registry.register_legacy(LegacyPersistenceProvider())
    ordered_manifests = tuple(manifest for _, manifest in resolved_definitions)
    for definition, manifest in resolved_definitions:
        if definition.persistence is None:
            if manifest.persistence is not None:
                raise ModulePersistenceError(
                    "The manifest declares persistence but the passive definition does not.",
                    module_id=manifest.id,
                    schema=manifest.persistence.schema_name,
                )
            continue
        registry.register(manifest, definition.persistence)
    registry.seal(ordered_manifests)
    return registry


def resolve_migration_source(source: ModuleMigrationSource, *, module_id: str) -> Path:
    """Löse ausschließlich Ressourcen bereits installierter Python-Pakete auf."""

    try:
        package_root_resource = resources.files(source.package)
        resource = package_root_resource.joinpath(source.resource)
    except (AttributeError, ModuleNotFoundError, TypeError) as exc:
        raise ModulePersistenceError(
            "The installed migration package could not be resolved.", module_id=module_id
        ) from exc
    package_root = Path(str(package_root_resource)).resolve()
    path = Path(str(resource)).resolve()
    if not path.is_relative_to(package_root) or not path.is_dir():
        raise ModulePersistenceError(
            "The installed migration resource is not a directory.", module_id=module_id
        )
    return path


def migration_log_fields(
    *, module_id: str, revision: str | None, schema: str | None, phase: str
) -> dict[str, str | None]:
    return {
        "module_id": module_id,
        "revision": revision,
        "schema": schema,
        "migration_phase": phase,
    }


def include_autogenerate_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Verhindere implizite Drops von nicht registrierten DB-Objekten."""

    del object_, name
    destructive_types = {
        "table",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
        "check_constraint",
    }
    return not (reflected and compare_to is None and type_ in destructive_types)


__all__ = [
    "HostDatabaseSessionProvider",
    "LegacyPersistenceProvider",
    "PersistenceRegistry",
    "RegisteredPersistence",
    "build_persistence_registry",
    "include_autogenerate_object",
    "migration_log_fields",
    "resolve_migration_source",
    "revision_namespace_for",
]

"""Alembic-Preflight für installierte, passiv registrierte Modulmigrationen."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.platform.modules.errors import ModulePersistenceError
from app.platform.modules.persistence import (
    PersistenceRegistry,
    migration_log_fields,
    resolve_migration_source,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MigrationStep:
    module_id: str
    schema: str | None
    revision: str


class MigrationCoordinator:
    """Validiert einen global linearen Host-/Modul-Revisionsgraphen."""

    def __init__(self, config: Config, registry: PersistenceRegistry) -> None:
        self._config = config
        self._registry = registry
        self._config.attributes["configure_logger"] = False

    def preflight(self) -> tuple[MigrationStep, ...]:
        host_versions = self._host_versions_path()
        source_paths: list[tuple[str, Path, str, str | None]] = []
        for module_id, source in self._registry.migration_sources:
            schema = next(
                contribution.schema
                for contribution in self._registry.contributions
                if contribution.module_id == module_id
            )
            path = resolve_migration_source(source, module_id=module_id)
            logger.info(
                "Module migration preflight source resolved",
                extra=migration_log_fields(
                    module_id=module_id,
                    revision=None,
                    schema=schema,
                    phase="preflight",
                ),
            )
            source_paths.append(
                (
                    module_id,
                    path,
                    source.revision_namespace,
                    schema,
                )
            )

        locations = (host_versions, *(path for _, path, _, _ in source_paths))
        self._config.set_main_option("version_locations", "\n".join(map(str, locations)))
        self._config.set_main_option("path_separator", "newline")
        scripts = ScriptDirectory.from_config(self._config)
        heads = scripts.get_heads()
        if len(heads) != 1:
            raise ModulePersistenceError(
                f"Exactly one global Alembic head is required, found: {', '.join(heads)}."
            )

        roots = {module_id: path for module_id, path, _, _ in source_paths}
        namespaces = {module_id: namespace for module_id, _, namespace, _ in source_paths}
        schemas = {module_id: schema for module_id, _, _, schema in source_paths}
        expected_order = [module_id for module_id, _ in self._registry.migration_sources]
        steps: list[MigrationStep] = []
        seen_modules: set[str] = set()
        first_module_order: list[str] = []

        revisions = tuple(reversed(tuple(scripts.walk_revisions(base="base", head="heads"))))
        for revision in revisions:
            revision_path = Path(revision.path).resolve()
            owner = next(
                (
                    module_id
                    for module_id, root in roots.items()
                    if revision_path.is_relative_to(root)
                ),
                "host",
            )
            if owner != "host":
                namespace = namespaces[owner]
                if not revision.revision.startswith(f"{namespace}_"):
                    raise ModulePersistenceError(
                        f'Revision "{revision.revision}" must start with "{namespace}_".',
                        module_id=owner,
                        schema=schemas[owner],
                    )
                if owner not in seen_modules:
                    seen_modules.add(owner)
                    first_module_order.append(owner)
            if not steps or steps[-1].module_id != owner:
                steps.append(MigrationStep(owner, schemas.get(owner), revision.revision))
            else:
                steps[-1] = MigrationStep(owner, schemas.get(owner), revision.revision)

        missing = [module_id for module_id in expected_order if module_id not in seen_modules]
        if missing:
            raise ModulePersistenceError(
                "Migration source contains no revisions.", module_id=missing[0]
            )
        if first_module_order != expected_order:
            misplaced = next(
                module_id
                for index, module_id in enumerate(first_module_order)
                if index >= len(expected_order) or module_id != expected_order[index]
            )
            raise ModulePersistenceError(
                "Initial module revisions do not follow the resolved dependency order.",
                module_id=misplaced,
                schema=schemas.get(misplaced),
            )
        return tuple(steps)

    def upgrade(self) -> tuple[MigrationStep, ...]:
        """Führe ausstehende Host-/Modulgruppen vor Aktivierung geordnet aus."""

        plan = self.preflight()
        scripts = ScriptDirectory.from_config(self._config)
        revisions = tuple(reversed(tuple(scripts.walk_revisions(base="base", head="heads"))))
        position = {revision.revision: index for index, revision in enumerate(revisions)}
        current_heads = asyncio.run(self._current_heads())
        if len(current_heads) > 1:
            raise ModulePersistenceError(
                "The database has multiple current revisions; coordinated upgrade stopped."
            )
        current = current_heads[0] if current_heads else None
        if current is not None and current not in position:
            raise ModulePersistenceError(
                f'The current database revision "{current}" is not in the installed graph.'
            )
        current_position = position[current] if current is not None else -1

        for step in plan:
            if position[step.revision] <= current_position:
                continue
            fields = {
                "module_id": step.module_id,
                "revision": step.revision,
                "schema": step.schema,
                "migration_phase": "upgrade_started",
            }
            logger.info("Module migration upgrade started", extra=fields)
            try:
                command.upgrade(self._config, step.revision)
            except Exception as exc:
                logger.exception(
                    "Module migration upgrade failed",
                    extra={**fields, "migration_phase": "upgrade_failed"},
                )
                raise ModulePersistenceError(
                    f'Migration to revision "{step.revision}" failed.',
                    module_id=step.module_id,
                    schema=step.schema,
                    phase="upgrade_failed",
                ) from exc
            logger.info(
                "Module migration upgrade completed",
                extra={**fields, "migration_phase": "upgrade_completed"},
            )
            current_position = position[step.revision]
        return plan

    def downgrade(self, target_revision: str) -> None:
        """Führe ausschließlich einen explizit angegebenen Alembic-Downgrade aus."""

        if not target_revision:
            raise ValueError("An explicit downgrade target revision is required.")
        self.preflight()
        scripts = ScriptDirectory.from_config(self._config)
        target = scripts.get_revision(target_revision)
        if target is None:
            raise ModulePersistenceError(
                f'Unknown explicit downgrade target "{target_revision}".', phase="downgrade"
            )
        command.downgrade(self._config, target_revision)

    async def _current_heads(self) -> tuple[str, ...]:
        database_url = self._config.attributes.get(
            "database_url", self._config.get_main_option("sqlalchemy.url")
        )
        if not database_url:
            raise ModulePersistenceError("Alembic database URL is not configured.")
        self._config.attributes["database_url"] = database_url
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync_connection: tuple(
                        MigrationContext.configure(sync_connection).get_current_heads()
                    )
                )
        finally:
            await engine.dispose()

    def _host_versions_path(self) -> Path:
        script_location = self._config.get_main_option("script_location")
        if not script_location:
            raise ModulePersistenceError("Alembic script_location is not configured.")
        root = Path(script_location)
        if not root.is_absolute():
            config_path = Path(self._config.config_file_name or ".").resolve()
            root = config_path.parent / root
        versions = (root / "versions").resolve()
        if not versions.is_dir():
            raise ModulePersistenceError("The host Alembic versions directory is missing.")
        return versions


__all__ = ["MigrationCoordinator", "MigrationStep"]

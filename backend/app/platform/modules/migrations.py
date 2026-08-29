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


def _load_revision_inventory(scripts: ScriptDirectory):
    """Load every source file before Alembic's revision map hides duplicate IDs."""

    # There is no public Alembic API that inventories duplicate revision files:
    # RevisionMap resolves them by ID first. Keep the private call isolated here.
    # backend/uv.lock pins Alembic 1.19.1 and the duplicate-source regression test
    # guards this compatibility boundary when that pin is updated.
    return scripts._load_revisions()


@dataclass(frozen=True, slots=True)
class MigrationStep:
    module_id: str
    schema: str | None
    revision: str


@dataclass(frozen=True, slots=True)
class _ModuleMigrationLocation:
    module_id: str
    path: Path
    revision_namespace: str
    adopted_revisions: frozenset[str]
    schema: str | None


class MigrationCoordinator:
    """Validiert einen global linearen Host-/Modul-Revisionsgraphen."""

    def __init__(self, config: Config, registry: PersistenceRegistry) -> None:
        self._config = config
        self._registry = registry
        self._config.attributes["configure_logger"] = False

    def preflight(self) -> tuple[MigrationStep, ...]:
        host_versions = self._host_versions_path()
        source_paths: list[_ModuleMigrationLocation] = []
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
                _ModuleMigrationLocation(
                    module_id=module_id,
                    path=path,
                    revision_namespace=source.revision_namespace,
                    adopted_revisions=source.adopted_revisions,
                    schema=schema,
                )
            )

        duplicate_paths: dict[Path, list[str]] = {}
        for source in source_paths:
            duplicate_paths.setdefault(source.path, []).append(source.module_id)
        shared_paths = [
            (path, module_ids)
            for path, module_ids in duplicate_paths.items()
            if len(module_ids) > 1
        ]
        if shared_paths:
            path, module_ids = min(shared_paths, key=lambda item: str(item[0]))
            raise ModulePersistenceError(
                f'Migration source path "{path}" is declared by multiple modules: '
                f"{', '.join(sorted(module_ids))}.",
                module_id=min(module_ids),
                phase="adoption_validation",
            )

        locations = (host_versions, *(source.path for source in source_paths))
        self._config.set_main_option("version_locations", "\n".join(map(str, locations)))
        self._config.set_main_option("path_separator", "newline")
        scripts = ScriptDirectory.from_config(self._config)
        self._validate_source_ownership(scripts, host_versions, tuple(source_paths))
        heads = scripts.get_heads()
        if len(heads) != 1:
            raise ModulePersistenceError(
                f"Exactly one global Alembic head is required, found: {', '.join(heads)}."
            )

        roots = {source.module_id: source.path for source in source_paths}
        schemas = {source.module_id: source.schema for source in source_paths}
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
            if owner != "host" and owner not in seen_modules:
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

    def _validate_source_ownership(
        self,
        scripts: ScriptDirectory,
        host_versions: Path,
        module_sources: tuple[_ModuleMigrationLocation, ...],
    ) -> None:
        """Inventarisiere Quellen mit Alembics Loader, bevor der Graph aufgelöst wird."""

        roots = (("host", host_versions),) + tuple(
            (source.module_id, source.path) for source in module_sources
        )
        schemas = {source.module_id: source.schema for source in module_sources}
        revisions_by_owner: dict[str, set[str]] = {
            owner: set() for owner, _ in roots
        }
        owners_by_revision: dict[str, list[str]] = {}

        # Alembic bleibt für das Laden der Revision-Metadaten und den Graphen
        # authoritative. Die rohe Inventur ist nötig, weil RevisionMap doppelte
        # IDs andernfalls nur warnt und abhängig von der Ladereihenfolge auflöst.
        loaded = sorted(
            _load_revision_inventory(scripts),
            key=lambda revision: (revision.revision, str(Path(revision.path).resolve())),
        )
        for revision in loaded:
            revision_path = Path(revision.path).resolve()
            owner = next(
                (
                    candidate
                    for candidate, root in roots
                    if revision_path.is_relative_to(root)
                ),
                None,
            )
            if owner is None:
                raise ModulePersistenceError(
                    f'Revision "{revision.revision}" is outside every configured migration source.',
                    phase="adoption_validation",
                )
            revisions_by_owner[owner].add(revision.revision)
            owners_by_revision.setdefault(revision.revision, []).append(owner)

        duplicates = sorted(
            revision
            for revision, owners in owners_by_revision.items()
            if len(owners) > 1
        )
        if duplicates:
            revision = duplicates[0]
            owners = owners_by_revision[revision]
            module_id = next((owner for owner in owners if owner != "host"), "host")
            owner_labels = [
                "host" if owner == "host" else f'module "{owner}"'
                for owner in owners
            ]
            raise ModulePersistenceError(
                f'Revision "{revision}" is provided by multiple migration sources: '
                f"{', '.join(owner_labels)}.",
                module_id=module_id,
                schema=schemas.get(module_id),
                phase="adoption_validation",
            )

        for source in module_sources:
            found = revisions_by_owner[source.module_id]
            missing = sorted(source.adopted_revisions.difference(found))
            if missing:
                raise ModulePersistenceError(
                    f'Adopted revision "{missing[0]}" is declared but missing from the '
                    "module migration source.",
                    module_id=source.module_id,
                    schema=source.schema,
                    phase="adoption_validation",
                )
            invalid = sorted(
                revision
                for revision in found.difference(source.adopted_revisions)
                if not revision.startswith(f"{source.revision_namespace}_")
            )
            if invalid:
                raise ModulePersistenceError(
                    f'Revision "{invalid[0]}" must be explicitly adopted or start with '
                    f'"{source.revision_namespace}_".',
                    module_id=source.module_id,
                    schema=source.schema,
                    phase="adoption_validation",
                )
            for revision in sorted(source.adopted_revisions):
                logger.info(
                    "Historical module migration adoption validated",
                    extra=migration_log_fields(
                        module_id=source.module_id,
                        revision=revision,
                        schema=source.schema,
                        phase="adoption_validation",
                    ),
                )

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

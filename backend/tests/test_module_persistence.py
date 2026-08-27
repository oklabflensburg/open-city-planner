import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi import FastAPI
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, MetaData, String, Table, func, insert, select, text, true
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.cli import module_migrations as migration_cli
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.modules.reference.module import DEFINITION as REFERENCE_DEFINITION
from app.platform.modules import (
    DuplicatePersistenceSchemaError,
    ModuleDefinition,
    ModuleMigrationSource,
    ModulePersistenceContribution,
    ModulePersistenceError,
    ModuleStartupError,
    parse_manifest,
    resolve_module_definitions,
    validate_manifests,
)
from app.platform.modules.migrations import MigrationCoordinator
from app.platform.modules.persistence import (
    HostDatabaseSessionProvider,
    PersistenceRegistry,
    build_persistence_registry,
    include_autogenerate_object,
    resolve_available_persistence_definitions,
    resolve_migration_source,
    revision_namespace_for,
)
from tests.fixtures.example_backend_module import DEFINITION as EXAMPLE_DEFINITION
from tests.fixtures.example_persistence_module import DEFINITION as DEPENDENT_DEFINITION
from tests.test_module_runtime import FakeDiscovery, definition, runtime_for

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FakeAvailableDiscovery(FakeDiscovery):
    def discover_available(self):
        return self.definitions


def module_manifest(
    module_id: str,
    schema: str,
    *,
    dependencies: dict[str, str] | None = None,
    migrations: bool = False,
):
    return parse_manifest(
        {
            "manifest_version": 1,
            "id": module_id,
            "name": module_id,
            "version": "1.0.0",
            "requires": {
                "host": ">=0.2.0,<1.0.0",
                "sdk": ">=1.0.0,<2.0.0",
                "modules": dependencies or {},
            },
            "persistence": {"schema": schema, "migrations": migrations},
        }
    )


def module_definition(
    manifest,
    metadata: MetaData,
    *,
    migration_resource: str | None = None,
) -> ModuleDefinition:
    def forbidden_loader():
        raise AssertionError("Persistence discovery must not instantiate module runtime code")

    return ModuleDefinition(
        manifest=manifest,
        loader=forbidden_loader,
        origin=f"tests.{manifest.id}",
        declared_id=manifest.id,
        persistence=ModulePersistenceContribution(
            module_id=manifest.id,
            metadata=metadata,
            schema=manifest.persistence.schema_name,
            migration_source=(
                ModuleMigrationSource(
                    package="tests.fixtures",
                    resource=migration_resource,
                    revision_namespace=revision_namespace_for(manifest.id),
                )
                if migration_resource is not None
                else None
            ),
        ),
    )


def module_metadata(schema: str, *, table_name: str = "items") -> MetaData:
    metadata = MetaData()
    Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(80), nullable=False),
        schema=schema,
    )
    return metadata


def test_registry_aggregates_legacy_and_two_metadata_sets_in_dependency_order() -> None:
    manifest_a = module_manifest("example-a", "example_a")
    manifest_b = module_manifest(
        "example-b",
        "example_b",
        dependencies={"example-a": ">=1.0.0,<2.0.0"},
    )
    definition_a = module_definition(manifest_a, module_metadata("example_a"))
    definition_b = module_definition(manifest_b, module_metadata("example_b"))

    resolved = resolve_module_definitions(
        enabled_module_ids=("example-b", "example-a"),
        discovery_providers=(FakeDiscovery((definition_b, definition_a)),),
        host_version="0.2.0",
    )
    registry = build_persistence_registry(resolved)

    assert [item.module_id for item in registry.contributions] == [
        "host-legacy",
        "example-a",
        "example-b",
    ]
    assert registry.target_metadata[0] is Base.metadata
    assert registry.owned_schemas == frozenset({"example_a", "example_b"})


def test_public_sdk_fixture_modules_register_two_persistence_sets() -> None:
    resolved = resolve_module_definitions(
        enabled_module_ids=("test-persistence-dependent", "test-example-module"),
        discovery_providers=(
            FakeDiscovery((DEPENDENT_DEFINITION, EXAMPLE_DEFINITION)),
        ),
        host_version="0.2.0",
    )

    registry = build_persistence_registry(resolved, include_legacy=False)

    assert [item.module_id for item in registry.contributions] == [
        "test-example-module",
        "test-persistence-dependent",
    ]
    assert {
        table.fullname
        for metadata in registry.target_metadata
        for table in metadata.tables.values()
    } == {
        "test_example_module.items",
        "test_persistence_dependent.items",
    }


def test_independent_module_persistence_is_ordered_lexicographically() -> None:
    manifest_b = module_manifest("example-b", "example_b")
    manifest_a = module_manifest("example-a", "example_a")
    definitions = (
        module_definition(manifest_b, module_metadata("example_b")),
        module_definition(manifest_a, module_metadata("example_a")),
    )

    resolved = resolve_module_definitions(
        enabled_module_ids=("example-b", "example-a"),
        discovery_providers=(FakeDiscovery(definitions),),
        host_version="0.2.0",
    )
    registry = build_persistence_registry(resolved, include_legacy=False)

    assert [item.module_id for item in registry.contributions] == ["example-a", "example-b"]


def test_available_migration_resolution_ignores_disabled_runtime_compatibility() -> None:
    manifest_data = REFERENCE_DEFINITION.manifest.model_dump(by_alias=True)
    manifest_data["requires"] = {
        **manifest_data["requires"],
        "host": ">=99.0.0,<100.0.0",
        "sdk": ">=99.0.0,<100.0.0",
    }
    incompatible = replace(REFERENCE_DEFINITION, manifest=manifest_data)

    resolved = resolve_available_persistence_definitions(
        (FakeAvailableDiscovery((incompatible,)),)
    )

    assert [(definition.declared_id, manifest.id) for definition, manifest in resolved] == [
        ("reference", "reference")
    ]


def test_duplicate_module_registration_is_rejected() -> None:
    manifest = module_manifest("example-a", "example_a")
    contribution = module_definition(manifest, module_metadata("example_a")).persistence
    assert contribution is not None
    registry = PersistenceRegistry()
    registry.register(manifest, contribution)

    with pytest.raises(ModulePersistenceError, match="already registered"):
        registry.register(manifest, contribution)


def test_duplicate_schema_ownership_is_rejected_by_manifest_contract() -> None:
    manifests = (
        module_manifest("example-a", "shared_schema"),
        module_manifest("example-b", "shared_schema"),
    )

    with pytest.raises(DuplicatePersistenceSchemaError) as captured:
        validate_manifests(manifests, host_version="0.2.0", sdk_version="1.1.0")

    assert captured.value.schema == "shared_schema"
    assert captured.value.module_ids == ("example-a", "example-b")


def test_module_metadata_cannot_own_tables_outside_declared_schema() -> None:
    manifest = module_manifest("example-a", "example_a")
    contribution = ModulePersistenceContribution(
        module_id="example-a",
        metadata=module_metadata("other_schema"),
        schema="example_a",
    )

    with pytest.raises(ModulePersistenceError, match="outside its owned schema"):
        PersistenceRegistry().register(manifest, contribution)


def test_existing_unqualified_table_can_be_adopted_explicitly() -> None:
    manifest = module_manifest("example-a", "example_a")
    metadata = MetaData()
    Table("existing_items", metadata, Column("id", Integer, primary_key=True))
    contribution = ModulePersistenceContribution(
        module_id="example-a",
        metadata=metadata,
        schema="example_a",
        adopted_tables=frozenset({"existing_items"}),
    )
    registry = PersistenceRegistry()

    registry.register(manifest, contribution)
    registry.seal((manifest,))

    assert registry.contributions[0].adopted_tables == frozenset({"existing_items"})
    assert registry.target_metadata == ()


def test_adopted_table_declaration_must_match_metadata() -> None:
    manifest = module_manifest("example-a", "example_a")
    contribution = ModulePersistenceContribution(
        module_id="example-a",
        metadata=MetaData(),
        schema="example_a",
        adopted_tables=frozenset({"existing_items"}),
    )

    with pytest.raises(ModulePersistenceError, match="exactly match"):
        PersistenceRegistry().register(manifest, contribution)


@pytest.mark.parametrize("table_name", ("public.items", "Items", "items-name"))
def test_adopted_table_names_must_be_unqualified_identifiers(table_name: str) -> None:
    with pytest.raises(ValueError, match="unqualified PostgreSQL identifiers"):
        ModulePersistenceContribution(
            module_id="example-a",
            metadata=MetaData(),
            schema="example_a",
            adopted_tables=frozenset({table_name}),
        )


@pytest.mark.parametrize(
    "resource",
    ("../migrations", "/tmp/migrations", "https://example.invalid/migrations"),
)
def test_migration_sources_reject_external_or_escaping_resources(resource: str) -> None:
    with pytest.raises(ValueError, match="relative installed-package"):
        ModuleMigrationSource(
            package="tests.fixtures",
            resource=resource,
            revision_namespace="mod_example_a",
        )


def test_unresolvable_migration_source_reports_module_id() -> None:
    source = ModuleMigrationSource(
        package="tests.fixtures",
        resource="missing_migrations",
        revision_namespace="mod_example_a",
    )

    with pytest.raises(ModulePersistenceError) as captured:
        resolve_migration_source(source, module_id="example-a")

    assert captured.value.module_id == "example-a"
    assert captured.value.phase == "preflight"


def test_revision_namespace_is_stable_and_namespaced() -> None:
    assert revision_namespace_for("analysis-areas") == "mod_analysis_areas"


@pytest.mark.parametrize(
    "object_type",
    ("table", "index", "unique_constraint", "foreign_key_constraint", "check_constraint"),
)
def test_autogenerate_never_proposes_implicit_drop_for_unowned_object(
    object_type: str,
) -> None:
    assert not include_autogenerate_object(
        object(), "legacy_object", object_type, reflected=True, compare_to=None
    )
    assert include_autogenerate_object(
        object(), "owned_object", object_type, reflected=True, compare_to=object()
    )


def test_migration_preflight_combines_host_and_modules_in_dependency_order() -> None:
    manifest_a = module_manifest("example-a", "example_a", migrations=True)
    manifest_b = module_manifest(
        "example-b",
        "example_b",
        dependencies={"example-a": ">=1.0.0,<2.0.0"},
        migrations=True,
    )
    definitions = (
        module_definition(
            manifest_b,
            module_metadata("example_b"),
            migration_resource="module_migrations/example_b",
        ),
        module_definition(
            manifest_a,
            module_metadata("example_a"),
            migration_resource="module_migrations/example_a",
        ),
    )
    resolved = resolve_module_definitions(
        enabled_module_ids=("example-b", "example-a"),
        discovery_providers=(FakeDiscovery(definitions),),
        host_version="0.2.0",
    )
    registry = build_persistence_registry(resolved, include_legacy=False)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    plan = MigrationCoordinator(config, registry).preflight()

    assert [(step.module_id, step.revision) for step in plan[-3:]] == [
        ("host", "20260825_0034"),
        ("example-a", "mod_example_a_20260825_0001"),
        ("example-b", "mod_example_b_20260825_0001"),
    ]


def migration_registry(*, module_b_resource: str) -> PersistenceRegistry:
    manifest_a = module_manifest("example-a", "example_a", migrations=True)
    manifest_b = module_manifest(
        "example-b",
        "example_b",
        dependencies={"example-a": ">=1.0.0,<2.0.0"},
        migrations=True,
    )
    definitions = (
        module_definition(
            manifest_b,
            module_metadata("example_b"),
            migration_resource=module_b_resource,
        ),
        module_definition(
            manifest_a,
            module_metadata("example_a"),
            migration_resource="module_migrations/example_a",
        ),
    )
    resolved = resolve_module_definitions(
        enabled_module_ids=("example-b", "example-a"),
        discovery_providers=(FakeDiscovery(definitions),),
        host_version="0.2.0",
    )
    return build_persistence_registry(resolved, include_legacy=False)


@pytest_asyncio.fixture
async def fresh_database_url() -> AsyncIterator[str]:
    base_url = make_url(get_settings().database_url)
    admin_url = base_url.set(database="postgres")
    database_name = f"test_module_migrations_{uuid.uuid4().hex}"
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    except (ConnectionError, DBAPIError, OSError, OperationalError) as exc:
        await admin.dispose()
        pytest.skip(f"PostgreSQL database creation is unavailable: {type(exc).__name__}")

    database_url = database_url_for(base_url, database_name)
    try:
        yield database_url
    finally:
        async with admin.connect() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname = '{database_name}' AND pid <> pg_backend_pid()"
                )
            )
            await connection.execute(text(f'DROP DATABASE "{database_name}"'))
        await admin.dispose()


def database_url_for(base_url: URL, database_name: str) -> str:
    """Ersetze nur den DB-Namen und erhalte Credentials für echte Verbindungen."""

    return base_url.set(database=database_name).render_as_string(hide_password=False)


def test_database_url_for_preserves_credentials_and_connection_options() -> None:
    password_marker = "credential-marker"
    base_url = URL.create(
        "postgresql+asyncpg",
        username="ci-user",
        password=password_marker,
        host="127.0.0.1",
        port=5432,
        database="base_db",
        query={"ssl": "require"},
    )

    derived_url = make_url(database_url_for(base_url, "temporary_db"))

    assert derived_url.drivername == base_url.drivername
    assert derived_url.username == base_url.username
    assert derived_url.password == password_marker
    assert derived_url.host == base_url.host
    assert derived_url.port == base_url.port
    assert derived_url.query == base_url.query
    assert derived_url.database == "temporary_db"


def migration_coordinator(
    database_url: str, *, module_b_resource: str = "module_migrations/example_b"
) -> MigrationCoordinator:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url"] = database_url
    return MigrationCoordinator(
        config,
        migration_registry(module_b_resource=module_b_resource),
    )


@pytest.mark.asyncio
async def test_fresh_upgrade_explicit_downgrade_and_reupgrade_module_migrations(
    fresh_database_url: str,
) -> None:
    coordinator = migration_coordinator(fresh_database_url)

    await asyncio.to_thread(coordinator.upgrade)
    engine = create_async_engine(fresh_database_url)
    async with engine.connect() as connection:
        schemas = set(
            await connection.scalars(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name IN ('example_a', 'example_b')"
                )
            )
        )
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert schemas == {"example_a", "example_b"}
    assert revision == "mod_example_b_20260825_0001"

    await asyncio.to_thread(coordinator.downgrade, "mod_example_a_20260825_0001")
    async with engine.connect() as connection:
        schemas = set(
            await connection.scalars(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name IN ('example_a', 'example_b')"
                )
            )
        )
    assert schemas == {"example_a"}

    await asyncio.to_thread(coordinator.upgrade)
    async with engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision == "mod_example_b_20260825_0001"
    await engine.dispose()


@pytest.mark.asyncio
async def test_reference_module_migration_up_down_and_seed_data(
    fresh_database_url: str,
) -> None:
    resolved = resolve_module_definitions(
        enabled_module_ids=("reference",),
        discovery_providers=(FakeDiscovery((REFERENCE_DEFINITION,)),),
        host_version="0.2.0",
    )
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = fresh_database_url
    coordinator = MigrationCoordinator(config, build_persistence_registry(resolved))

    await asyncio.to_thread(coordinator.upgrade)
    engine = create_async_engine(fresh_database_url)
    async with engine.connect() as connection:
        count = await connection.scalar(text("SELECT count(*) FROM reference.items"))
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert count == 2
    assert revision == "mod_reference_20260826_0001"

    await asyncio.to_thread(coordinator.downgrade, "20260825_0034")
    async with engine.connect() as connection:
        schema = await connection.scalar(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = 'reference'"
            )
        )
    assert schema is None

    await asyncio.to_thread(coordinator.upgrade)
    async with engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision == "mod_reference_20260826_0001"
    await engine.dispose()


@pytest.mark.asyncio
async def test_reference_module_disable_and_reenable_keep_graph_revision_and_data(
    fresh_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = resolve_module_definitions(
        enabled_module_ids=("reference",),
        discovery_providers=(FakeDiscovery((REFERENCE_DEFINITION,)),),
        host_version="0.2.0",
    )
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = fresh_database_url
    coordinator = MigrationCoordinator(config, build_persistence_registry(enabled))
    await asyncio.to_thread(coordinator.upgrade)

    engine = create_async_engine(fresh_database_url)
    async with engine.connect() as connection:
        before_disable = await connection.scalar(text("SELECT count(*) FROM reference.items"))
        enabled_revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))

    monkeypatch.setattr(
        migration_cli,
        "get_settings",
        lambda: Settings(enabled_modules="", database_url=fresh_database_url),
    )
    monkeypatch.setattr(
        "app.platform.modules.migrations.command.downgrade",
        lambda *_args, **_kwargs: pytest.fail("Disable must never invoke downgrade"),
    )
    disabled_coordinator = migration_cli.coordinator()
    disabled_plan = await asyncio.to_thread(disabled_coordinator.preflight)
    await asyncio.to_thread(disabled_coordinator.upgrade)
    async with engine.connect() as connection:
        while_disabled = await connection.scalar(text("SELECT count(*) FROM reference.items"))
        disabled_revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))

    monkeypatch.setattr(
        migration_cli,
        "get_settings",
        lambda: Settings(
            enabled_modules="reference", database_url=fresh_database_url
        ),
    )
    await asyncio.to_thread(migration_cli.coordinator().upgrade)
    async with engine.connect() as connection:
        after_reenable = await connection.scalar(text("SELECT count(*) FROM reference.items"))
        reenabled_revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert (disabled_plan[-1].module_id, disabled_plan[-1].revision) == (
        "reference",
        "mod_reference_20260826_0001",
    )
    assert enabled_revision == disabled_revision == reenabled_revision
    assert (before_disable, while_disabled, after_reenable) == (2, 2, 2)
    await engine.dispose()


@pytest.mark.asyncio
async def test_successful_migration_then_startup_failure_does_not_downgrade(
    fresh_database_url: str,
) -> None:
    resolved = resolve_module_definitions(
        enabled_module_ids=("reference",),
        discovery_providers=(FakeDiscovery((REFERENCE_DEFINITION,)),),
        host_version="0.2.0",
    )
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = fresh_database_url
    await asyncio.to_thread(
        MigrationCoordinator(config, build_persistence_registry(resolved)).upgrade
    )

    runtime = runtime_for(
        [
            definition(
                "failing-module",
                events=[],
                startup_error=RuntimeError("startup failed"),
            )
        ]
    )
    runtime.register(FastAPI())
    with pytest.raises(ModuleStartupError, match="startup"):
        await runtime.startup()

    engine = create_async_engine(fresh_database_url)
    async with engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        count = await connection.scalar(text("SELECT count(*) FROM reference.items"))
    assert revision == "mod_reference_20260826_0001"
    assert count == 2
    await engine.dispose()


def test_downgrade_requires_an_explicit_target_before_preflight() -> None:
    coordinator = migration_coordinator("postgresql+asyncpg://unused:unused@localhost/unused")

    with pytest.raises(ValueError, match="explicit downgrade target"):
        coordinator.downgrade("")


@pytest.mark.asyncio
async def test_broken_module_migration_stops_with_module_context(
    fresh_database_url: str,
) -> None:
    coordinator = migration_coordinator(
        fresh_database_url,
        module_b_resource="module_migrations/example_b_broken",
    )

    with pytest.raises(ModulePersistenceError) as captured:
        await asyncio.to_thread(coordinator.upgrade)

    assert captured.value.module_id == "example-b"
    assert captured.value.schema == "example_b"
    assert captured.value.phase == "upgrade_failed"
    engine = create_async_engine(fresh_database_url)
    async with engine.connect() as connection:
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert revision == "mod_example_a_20260825_0001"
    await engine.dispose()


@dataclass(frozen=True, slots=True)
class SchemaFixture:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    schema_a: str
    schema_b: str
    metadata_a: MetaData
    metadata_b: MetaData
    table_a: Table
    table_b: Table


@pytest_asyncio.fixture
async def postgres_schemas() -> AsyncIterator[SchemaFixture]:
    suffix = uuid.uuid4().hex[:12]
    schema_a = f"test_module_a_{suffix}"
    schema_b = f"test_module_b_{suffix}"
    engine = create_async_engine(make_url(get_settings().database_url))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_a}"'))
            await connection.execute(text(f'CREATE SCHEMA "{schema_b}"'))
    except (ConnectionError, DBAPIError, OSError, OperationalError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL test database is unavailable: {type(exc).__name__}")

    metadata_a = MetaData()
    metadata_b = MetaData()
    table_a = Table(
        "features",
        metadata_a,
        Column("id", Integer, primary_key=True),
        Column("name", String(80), nullable=False),
        Column("geometry", Geometry("POLYGON", srid=4326), nullable=False),
        schema=schema_a,
    )
    table_b = Table(
        "features",
        metadata_b,
        Column("id", Integer, primary_key=True),
        Column("name", String(80), nullable=False),
        Column("geometry", Geometry("POLYGON", srid=4326), nullable=False),
        schema=schema_b,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield SchemaFixture(
            engine,
            sessions,
            schema_a,
            schema_b,
            metadata_a,
            metadata_b,
            table_a,
            table_b,
        )
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_a}" CASCADE'))
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_b}" CASCADE'))
        await engine.dispose()


@pytest.mark.asyncio
async def test_autogenerate_sees_two_module_tables_without_false_legacy_drops(
    postgres_schemas: SchemaFixture,
) -> None:
    metadata = (postgres_schemas.metadata_a, postgres_schemas.metadata_b)

    def differences(sync_connection):
        context = MigrationContext.configure(
            sync_connection,
            opts={
                "include_schemas": True,
                "include_name": lambda name, type_, parents: (
                    name in {postgres_schemas.schema_a, postgres_schemas.schema_b}
                    if type_ == "schema"
                    else parents.get("schema_name")
                    in {postgres_schemas.schema_a, postgres_schemas.schema_b}
                ),
            },
        )
        return compare_metadata(context, metadata)

    async with postgres_schemas.engine.begin() as connection:
        before = await connection.run_sync(differences)
        await connection.run_sync(postgres_schemas.metadata_a.create_all)
        await connection.run_sync(postgres_schemas.metadata_b.create_all)
        after = await connection.run_sync(differences)

    added_tables = {operation[1].fullname for operation in before if operation[0] == "add_table"}
    assert added_tables == {
        f"{postgres_schemas.schema_a}.features",
        f"{postgres_schemas.schema_b}.features",
    }
    assert not [operation for operation in after if operation[0] in {"add_table", "remove_table"}]


@pytest.mark.asyncio
async def test_same_table_name_and_cross_schema_postgis_query_work(
    postgres_schemas: SchemaFixture,
) -> None:
    polygon = "POLYGON((9.4 54.7,9.5 54.7,9.5 54.8,9.4 54.8,9.4 54.7))"
    async with postgres_schemas.engine.begin() as connection:
        await connection.run_sync(postgres_schemas.metadata_a.create_all)
        await connection.run_sync(postgres_schemas.metadata_b.create_all)
        await connection.execute(
            insert(postgres_schemas.table_a).values(
                id=1, name="A", geometry=func.ST_GeomFromText(polygon, 4326)
            )
        )
        await connection.execute(
            insert(postgres_schemas.table_b).values(
                id=1, name="B", geometry=func.ST_GeomFromText(polygon, 4326)
            )
        )
        intersects = await connection.scalar(
            select(
                func.ST_Intersects(
                    postgres_schemas.table_a.c.geometry,
                    postgres_schemas.table_b.c.geometry,
                )
            ).select_from(postgres_schemas.table_a.join(postgres_schemas.table_b, true()))
        )

    assert intersects is True


@pytest.mark.asyncio
async def test_host_session_provider_commits_and_rolls_back(
    postgres_schemas: SchemaFixture,
) -> None:
    async with postgres_schemas.engine.begin() as connection:
        await connection.run_sync(postgres_schemas.metadata_a.create_all)
    provider = HostDatabaseSessionProvider(postgres_schemas.sessions)

    async with provider.session() as session:
        await session.execute(
            insert(postgres_schemas.table_a).values(
                id=1,
                name="kept",
                geometry=func.ST_GeomFromText(
                    "POLYGON((9.4 54.7,9.5 54.7,9.5 54.8,9.4 54.8,9.4 54.7))",
                    4326,
                ),
            )
        )

    with pytest.raises(RuntimeError, match="rollback"):
        async with provider.session() as session:
            await session.execute(
                insert(postgres_schemas.table_a).values(
                    id=2,
                    name="discarded",
                    geometry=func.ST_GeomFromText(
                        "POLYGON((9.4 54.7,9.5 54.7,9.5 54.8,9.4 54.8,9.4 54.7))",
                        4326,
                    ),
                )
            )
            raise RuntimeError("rollback")

    async with postgres_schemas.sessions() as session:
        names = tuple(await session.scalars(select(postgres_schemas.table_a.c.name)))
    assert names == ("kept",)


@pytest.mark.asyncio
async def test_disabling_module_does_not_drop_schema_or_data(
    postgres_schemas: SchemaFixture,
) -> None:
    async with postgres_schemas.engine.begin() as connection:
        await connection.run_sync(postgres_schemas.metadata_a.create_all)
        await connection.execute(
            insert(postgres_schemas.table_a).values(
                id=1,
                name="preserved",
                geometry=func.ST_GeomFromText(
                    "POLYGON((9.4 54.7,9.5 54.7,9.5 54.8,9.4 54.8,9.4 54.7))",
                    4326,
                ),
            )
        )

    disabled_registry = build_persistence_registry((), include_legacy=False)
    assert disabled_registry.contributions == ()
    async with postgres_schemas.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(postgres_schemas.table_a)) == 1

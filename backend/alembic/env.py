from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.platform.modules import EntryPointModuleDiscovery, FirstPartyModuleDiscovery
from app.platform.modules.persistence import (
    build_persistence_registry,
    include_autogenerate_object,
)
from app.platform.modules.runtime import resolve_module_definitions

settings = get_settings()
resolved_modules = resolve_module_definitions(
    enabled_module_ids=settings.enabled_module_list,
    discovery_providers=(FirstPartyModuleDiscovery(), EntryPointModuleDiscovery()),
    host_version=settings.api_version,
)
registry = build_persistence_registry(resolved_modules)

config = context.config
database_url = config.attributes.get("database_url", settings.database_url)
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = registry.target_metadata


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    """Reflektiere nur das Legacy-/Public-Schema und explizit registrierte Module."""

    if type_ == "schema":
        return name in {None, "public", *registry.owned_schemas}
    return parent_names.get("schema_name") in {None, "public", *registry.owned_schemas}


def configure_context(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        include_object=include_autogenerate_object,
        **kwargs,
    )


def run_migrations_offline() -> None:
    configure_context(
        url=database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    configure_context(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

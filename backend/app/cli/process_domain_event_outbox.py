import argparse
import asyncio
import os
import socket

from fastapi import FastAPI

from app.core.config import BACKEND_ENV_FILE, get_settings
from app.db.session import AsyncSessionLocal
from app.integrations.module_host_ports import (
    HostOsmSnapshotQueries,
    HostPolygonSpatialMatches,
)
from app.observability.jobs import observed_job
from app.platform.events import InProcessEventBus
from app.platform.events.jobs import domain_event_outbox_handler
from app.platform.modules import (
    EntryPointModuleDiscovery,
    FirstPartyModuleDiscovery,
    activate_enabled_module_python_paths,
    create_module_runtime,
)
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.jobs import JobRunner, LegacyJobAdapter
from app.platform.modules.persistence import HostDatabaseSessionProvider
from app.platform.modules.sdk import JobSchedule, RetryPolicy
from app.services.polygon_event_handlers import register_polygon_event_handlers


@observed_job("domain_event_outbox")
async def run(limit: int) -> dict[str, int]:
    settings = get_settings()
    bus = InProcessEventBus()
    register_polygon_event_handlers(bus)
    runtime = create_module_runtime(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=(
            FirstPartyModuleDiscovery(
                excluded_module_ids=settings.excluded_builtin_module_list
            ),
            EntryPointModuleDiscovery(),
        ),
        host_version=settings.api_version,
        context_factory=ModuleContextFactory(
            ModuleHostServices(
                database=HostDatabaseSessionProvider(),
                osm_snapshots=HostOsmSnapshotQueries(),
                polygon_spatial_matches=HostPolygonSpatialMatches(),
            ),
            event_bus=bus,
            module_env_file=BACKEND_ENV_FILE,
        ),
    )
    activate_enabled_module_python_paths()
    registry = runtime.job_registry
    assert registry is not None
    legacy_jobs = LegacyJobAdapter(registry, module_id="host-events")
    handler = domain_event_outbox_handler(
        bus,
        session_factory=AsyncSessionLocal,
        worker_id=f"{socket.gethostname()}:{os.getpid()}",
        limit=limit,
    )
    legacy_jobs.register(
        job_id="host-events.outbox-dispatch",
        handler=handler,
        retry=RetryPolicy(max_attempts=1),
        schedule=JobSchedule(interval_seconds=60),
    )
    runtime.register(FastAPI())
    bus.seal()
    await runtime.startup()
    try:
        result = await JobRunner(registry).run("host-events.outbox-dispatch")
        if not isinstance(result, dict):
            raise TypeError("The domain event outbox job returned an invalid result.")
        return result
    finally:
        await runtime.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fällige Domain-Event-Zustellungen aus der Outbox verarbeiten"
    )
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run(max(1, min(args.limit, 500))))


if __name__ == "__main__":
    main()

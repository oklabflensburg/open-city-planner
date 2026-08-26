import argparse
import asyncio
import os
import socket

from fastapi import FastAPI

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.observability.jobs import observed_job
from app.platform.events import InProcessEventBus, OutboxDispatcher
from app.platform.modules import (
    EntryPointModuleDiscovery,
    FirstPartyModuleDiscovery,
    create_module_runtime,
)
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.persistence import HostDatabaseSessionProvider
from app.services.polygon_event_handlers import register_polygon_event_handlers


@observed_job("domain_event_outbox")
async def run(limit: int) -> dict[str, int]:
    settings = get_settings()
    bus = InProcessEventBus()
    register_polygon_event_handlers(bus)
    runtime = create_module_runtime(
        enabled_module_ids=settings.enabled_module_list,
        discovery_providers=(FirstPartyModuleDiscovery(), EntryPointModuleDiscovery()),
        host_version=settings.api_version,
        context_factory=ModuleContextFactory(
            ModuleHostServices(database=HostDatabaseSessionProvider()), event_bus=bus
        ),
    )
    runtime.register(FastAPI())
    bus.seal()
    await runtime.startup()
    try:
        dispatcher = OutboxDispatcher(
            bus,
            worker_id=f"{socket.gethostname()}:{os.getpid()}",
        )
        async with AsyncSessionLocal() as session:
            return await dispatcher.run_once(session, limit=limit)
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

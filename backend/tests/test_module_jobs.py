import ast
import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from prometheus_client import generate_latest

from app.observability.metrics import (
    MODULE_JOB_DURATION,
    MODULE_JOB_FAILURES,
    MODULE_JOB_LAST_SUCCESS,
    MODULE_JOB_RETRIES,
    MODULE_JOB_RUNS,
    REGISTRY,
)
from app.platform.events import jobs as event_jobs
from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.contracts import ModuleDiscoveryProvider
from app.platform.modules.errors import (
    DuplicateJobRegistrationError,
    JobExecutionError,
    JobRegistryError,
    JobRegistrySealedError,
    JobTimeoutError,
    UnknownJobError,
)
from app.platform.modules.jobs import JobRegistry, JobRunner, LegacyJobAdapter
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    JobDefinition,
    JobSchedule,
    ModuleContext,
    ModuleDefinition,
    RetryPolicy,
    parse_manifest,
)
from app.platform.modules.testing import (
    FakeEventBus,
    FakeModuleSettings,
    FakeServiceRegistry,
    create_test_module_context,
)

FIXED_RUN_ID = UUID("00000000-0000-4000-8000-000000000100")


@dataclass(frozen=True)
class JobCompleted:
    event_type: str = "job-module.completed"
    event_version: int = 1


class RecordingMetric:
    def __init__(self) -> None:
        self.labels_calls: list[tuple[str, ...]] = []
        self.values: list[float] = []

    def labels(self, *values: str) -> "RecordingMetric":
        self.labels_calls.append(values)
        return self

    def inc(self) -> None:
        self.values.append(1)

    def observe(self, value: float) -> None:
        self.values.append(value)

    def set_to_current_time(self) -> None:
        self.values.append(1)


class RecordingJobMetrics:
    def __init__(self) -> None:
        self.runs = RecordingMetric()
        self.failures = RecordingMetric()
        self.retries = RecordingMetric()
        self.duration = RecordingMetric()
        self.last_success = RecordingMetric()


async def successful_handler(_context: ModuleContext) -> str:
    return "done"


def job(job_id: str = "example.refresh", **overrides) -> JobDefinition:
    return JobDefinition(job_id=job_id, handler=successful_handler, **overrides)


def test_registry_records_owner_descriptor_schedule_and_on_demand_job() -> None:
    registry = JobRegistry()
    context = create_test_module_context(module_id="example")
    scheduled = job(schedule=JobSchedule(interval_seconds=60))
    on_demand = job("example.rebuild")

    registry.register(module_id="example", definition=scheduled, context=context)
    registry.register(module_id="example", definition=on_demand, context=context)

    assert [(item.job_id, item.module_id) for item in registry.jobs] == [
        ("example.rebuild", "example"),
        ("example.refresh", "example"),
    ]
    assert registry.get("example.refresh").definition.schedule == JobSchedule(interval_seconds=60)
    assert registry.get("example.rebuild").definition.schedule is None


def test_duplicate_job_owner_and_sealed_registry_fail_fast() -> None:
    registry = JobRegistry()
    context = create_test_module_context(module_id="example")
    registry.register(module_id="example", definition=job(), context=context)

    with pytest.raises(DuplicateJobRegistrationError) as duplicate:
        registry.register(module_id="example", definition=job(), context=context)
    assert duplicate.value.job_id == "example.refresh"
    assert duplicate.value.provider_modules == ("example", "example")

    with pytest.raises(JobRegistryError, match="provider module namespace"):
        registry.register(module_id="foreign", definition=job("example.foreign"), context=context)

    registry.seal()
    assert registry.sealed
    with pytest.raises(JobRegistrySealedError):
        registry.register(module_id="example", definition=job("example.closed"), context=context)
    with pytest.raises(UnknownJobError):
        registry.get("example.unknown")


@pytest.mark.parametrize(
    "factory",
    (
        lambda: JobSchedule(interval_seconds=0),
        lambda: RetryPolicy(max_attempts=0),
        lambda: RetryPolicy(initial_delay_seconds=-1),
        lambda: JobDefinition(job_id="INVALID", handler=successful_handler),
        lambda: JobDefinition(
            job_id="example.timeout", handler=successful_handler, timeout_seconds=0
        ),
        lambda: JobDefinition(
            job_id="example.policy",
            handler=successful_handler,
            retry=None,  # type: ignore[arg-type]
        ),
    ),
)
def test_invalid_job_contract_is_rejected(factory) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory()


@dataclass
class FakeDiscovery(ModuleDiscoveryProvider):
    definitions: Sequence[ModuleDefinition]

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        return self.definitions


class JobModule:
    manifest = parse_manifest(
        {
            "manifest_version": 1,
            "id": "job-module",
            "name": "Job module",
            "version": "1.0.0",
            "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.5.0,<2.0.0"},
        }
    )

    def __init__(self, seen: list[ModuleContext]) -> None:
        self.seen = seen

    def register(self, context: ModuleContext) -> None:
        assert context.scheduler is not None

        async def execute(supplied_context: ModuleContext) -> str:
            self.seen.append(supplied_context)
            assert supplied_context.database is not None
            assert supplied_context.events is not None
            assert supplied_context.services is not None
            assert supplied_context.settings is not None
            assert supplied_context.settings.require("value") == "configured"
            await supplied_context.events.publish(JobCompleted())
            return "module-result"

        context.scheduler.register(
            JobDefinition(
                job_id="refresh",
                handler=execute,
                schedule=JobSchedule(interval_seconds=300),
            )
        )


def module_definition(seen: list[ModuleContext]) -> ModuleDefinition:
    return ModuleDefinition(
        manifest=JobModule.manifest,
        loader=lambda: JobModule(seen),
        origin="tests:job-module",
        declared_id="job-module",
    )


@pytest.mark.asyncio
async def test_enabled_module_registers_job_and_runner_supplies_complete_context() -> None:
    seen: list[ModuleContext] = []
    definition = module_definition(seen)
    database = object()
    events = FakeEventBus()
    services = FakeServiceRegistry()
    settings = FakeModuleSettings({"value": "configured"})
    runtime = create_module_runtime(
        enabled_module_ids=("job-module",),
        discovery_providers=(FakeDiscovery((definition,)),),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(
            ModuleHostServices(
                database=database,  # type: ignore[arg-type]
                events=events,
                services=services,
                settings=settings,
            )
        ),
    )
    runtime.register(FastAPI())
    assert runtime.job_registry is not None
    assert runtime.job_registry.sealed
    assert runtime.job_registry.jobs[0].job_id == "job-module.refresh"

    result = await JobRunner(runtime.job_registry).run("job-module.refresh")

    assert result == "module-result"
    assert seen == [runtime.registry.get("job-module").context]
    assert events.published == [JobCompleted()]


def test_disabled_module_contributes_no_jobs() -> None:
    runtime = create_module_runtime(
        enabled_module_ids=(),
        discovery_providers=(FakeDiscovery((module_definition([]),)),),
        host_version="0.2.0",
    )
    runtime.register(FastAPI())
    assert runtime.job_registry is not None
    assert runtime.job_registry.jobs == ()


@pytest.mark.asyncio
async def test_runner_retries_failed_handler_and_stops_at_max_attempts() -> None:
    attempts = 0

    async def failing(_context: ModuleContext) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("provider unavailable")

    definition = JobDefinition(
        job_id="example.retry",
        handler=failing,
        retry=RetryPolicy(max_attempts=3, initial_delay_seconds=0),
    )
    registry = sealed_registry(definition)
    metrics = RecordingJobMetrics()

    with pytest.raises(JobExecutionError) as error:
        await JobRunner(registry, metrics=metrics, run_id_factory=lambda: FIXED_RUN_ID).run(
            definition.job_id
        )

    assert attempts == 3
    assert error.value.attempt == 3
    assert len(metrics.failures.values) == 3
    assert len(metrics.retries.values) == 2
    assert metrics.runs.labels_calls == [("example", "example.retry", "failed")]


@pytest.mark.asyncio
async def test_timeout_is_a_failed_attempt_and_uses_retry_policy() -> None:
    attempts = 0

    async def hanging(_context: ModuleContext) -> None:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(1)

    definition = JobDefinition(
        job_id="example.timeout",
        handler=hanging,
        retry=RetryPolicy(max_attempts=2),
        timeout_seconds=0.01,
    )
    metrics = RecordingJobMetrics()

    with pytest.raises(JobTimeoutError) as error:
        await JobRunner(sealed_registry(definition), metrics=metrics).run(definition.job_id)

    assert attempts == 2
    assert error.value.attempt == 2
    assert len(metrics.failures.values) == 2
    assert len(metrics.retries.values) == 1


@pytest.mark.asyncio
async def test_handler_timeout_error_without_deadline_is_a_regular_failure() -> None:
    async def provider_timeout(_context: ModuleContext) -> None:
        raise TimeoutError("provider timeout")

    definition = JobDefinition(job_id="example.provider-timeout", handler=provider_timeout)

    with pytest.raises(JobExecutionError) as error:
        await JobRunner(sealed_registry(definition), metrics=RecordingJobMetrics()).run(
            definition.job_id
        )

    assert not isinstance(error.value, JobTimeoutError)


@pytest.mark.asyncio
async def test_failed_job_does_not_block_another_registered_job() -> None:
    async def failing(_context: ModuleContext) -> None:
        raise RuntimeError("isolated failure")

    registry = JobRegistry()
    context = create_test_module_context(module_id="example")
    registry.register(
        module_id="example",
        definition=JobDefinition(job_id="example.fail", handler=failing),
        context=context,
    )
    registry.register(module_id="example", definition=job("example.succeed"), context=context)
    registry.seal()
    runner = JobRunner(registry, metrics=RecordingJobMetrics())

    with pytest.raises(JobExecutionError):
        await runner.run("example.fail")

    assert await runner.run("example.succeed") == "done"


@pytest.mark.asyncio
async def test_success_updates_metrics_and_structured_logs(caplog) -> None:
    definition = job("example.observe")
    metrics = RecordingJobMetrics()
    runner = JobRunner(
        sealed_registry(definition),
        metrics=metrics,
        run_id_factory=lambda: FIXED_RUN_ID,
    )

    with caplog.at_level(logging.INFO):
        assert await runner.run(definition.job_id) == "done"

    succeeded = next(
        record for record in caplog.records if getattr(record, "job_phase", None) == "succeeded"
    )
    assert succeeded.module_id == "example"
    assert succeeded.job_id == "example.observe"
    assert succeeded.job_run_id == str(FIXED_RUN_ID)
    assert succeeded.job_attempt == 1
    assert succeeded.job_duration_ms >= 0
    assert metrics.runs.labels_calls == [("example", "example.observe", "succeeded")]
    assert metrics.last_success.labels_calls == [("example", "example.observe")]
    assert metrics.duration.values[0] >= 0


@pytest.mark.asyncio
async def test_prometheus_metrics_use_only_bounded_job_labels() -> None:
    definition = job("metrics-module.observe")
    registry = sealed_registry(definition, module_id="metrics-module")
    before = MODULE_JOB_RUNS.labels("metrics-module", definition.job_id, "succeeded")._value.get()

    await JobRunner(registry, run_id_factory=lambda: FIXED_RUN_ID).run(definition.job_id)

    assert (
        MODULE_JOB_RUNS.labels("metrics-module", definition.job_id, "succeeded")._value.get()
        == before + 1
    )
    assert MODULE_JOB_FAILURES.labels("metrics-module", definition.job_id)._value.get() == 0
    assert MODULE_JOB_RETRIES.labels("metrics-module", definition.job_id)._value.get() == 0
    assert (
        MODULE_JOB_DURATION.labels("metrics-module", definition.job_id, "succeeded")._sum.get() >= 0
    )
    assert MODULE_JOB_LAST_SUCCESS.labels("metrics-module", definition.job_id)._value.get() > 0
    assert str(FIXED_RUN_ID) not in generate_latest(REGISTRY).decode()


@pytest.mark.asyncio
async def test_default_concurrency_serializes_same_job() -> None:
    running = 0
    maximum = 0

    async def handler(_context: ModuleContext) -> None:
        nonlocal running, maximum
        running += 1
        maximum = max(maximum, running)
        await asyncio.sleep(0)
        running -= 1

    definition = JobDefinition(job_id="example.serial", handler=handler)
    runner = JobRunner(sealed_registry(definition), metrics=RecordingJobMetrics())

    await asyncio.gather(runner.run(definition.job_id), runner.run(definition.job_id))

    assert maximum == 1


@pytest.mark.asyncio
async def test_domain_event_outbox_pilot_uses_injected_worker_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, int]] = []
    session = object()

    class FakeSessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args) -> None:
            return None

    class FakeDispatcher:
        def __init__(self, _bus, *, worker_id: str) -> None:
            assert worker_id == "worker-1"

        async def run_once(self, supplied_session, *, limit: int):
            calls.append((supplied_session, limit))
            return {"processed": 2}

    monkeypatch.setattr(event_jobs, "OutboxDispatcher", FakeDispatcher)
    handler = event_jobs.domain_event_outbox_handler(
        FakeEventBus(),
        session_factory=FakeSessionContext,
        worker_id="worker-1",
        limit=25,
    )
    registry = JobRegistry()
    LegacyJobAdapter(registry, module_id="host-events").register(
        job_id="host-events.outbox-dispatch",
        handler=handler,
        schedule=JobSchedule(interval_seconds=60),
    )
    registry.seal()

    assert await JobRunner(registry, metrics=RecordingJobMetrics()).run(
        "host-events.outbox-dispatch"
    ) == {"processed": 2}
    assert calls == [(session, 25)]


def test_pilot_handler_has_no_forbidden_host_imports_and_deployment_command_is_stable() -> None:
    source = Path(event_jobs.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert imports.isdisjoint({"app.core.config", "app.db.session", "app.cache.redis"})

    root = Path(__file__).resolve().parents[2]
    ansible = (root / "deploy/ansible/roles/stadtplaner/tasks/main.yml").read_text(encoding="utf-8")
    command = "python -m app.cli.process_domain_event_outbox --limit 50"
    assert command in ansible


def sealed_registry(
    definition: JobDefinition,
    *,
    module_id: str = "example",
) -> JobRegistry:
    registry = JobRegistry()
    context = create_test_module_context(module_id=module_id)
    registry.register(module_id=module_id, definition=definition, context=context)
    registry.seal()
    return registry

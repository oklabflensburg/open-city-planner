"""Host-owned Registry und Runner für modulgebundene Background Jobs."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.observability.metrics import (
    MODULE_JOB_DURATION,
    MODULE_JOB_FAILURES,
    MODULE_JOB_LAST_SUCCESS,
    MODULE_JOB_RETRIES,
    MODULE_JOB_RUNS,
)
from app.platform.modules.errors import (
    DuplicateJobRegistrationError,
    JobExecutionError,
    JobRegistryError,
    JobRegistrySealedError,
    JobTimeoutError,
    UnknownJobError,
)
from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.sdk import (
    JobDefinition,
    JobSchedule,
    LegacyJobHandler,
    ModuleContext,
    RetryPolicy,
)

if TYPE_CHECKING:
    from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)
type Sleep = Callable[[float], Awaitable[None]]
type RunIdFactory = Callable[[], UUID]


class _JobAttemptTimedOut(TimeoutError):
    pass


@dataclass(frozen=True, slots=True)
class JobDescriptor:
    module_id: str
    definition: JobDefinition
    context: ModuleContext | None
    legacy: bool = False

    @property
    def job_id(self) -> str:
        return self.definition.job_id


class JobRegistry:
    """Runtime-skopierte Registry mit Ownership und deterministischer Reihenfolge."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobDescriptor] = {}
        self._sealed = False

    @property
    def jobs(self) -> tuple[JobDescriptor, ...]:
        return tuple(self._jobs[job_id] for job_id in sorted(self._jobs))

    @property
    def sealed(self) -> bool:
        return self._sealed

    def bind(self, manifest: ModuleManifestV1) -> "ModuleSchedulerAdapter":
        return ModuleSchedulerAdapter(self, manifest)

    def register(
        self,
        *,
        module_id: str,
        definition: JobDefinition,
        context: ModuleContext,
    ) -> None:
        self._register(module_id, definition, context=context, legacy=False)

    def register_legacy(
        self,
        *,
        module_id: str,
        definition: JobDefinition,
    ) -> None:
        """Expliziter Strangler-Adapter für bestehende zentrale Worker."""

        self._register(module_id, definition, context=None, legacy=True)

    def _register(
        self,
        module_id: str,
        definition: JobDefinition,
        *,
        context: ModuleContext | None,
        legacy: bool,
    ) -> None:
        if self._sealed:
            raise JobRegistrySealedError(
                "Job registration is closed.", job_id=definition.job_id, module_id=module_id
            )
        owner = definition.job_id.partition(".")[0]
        if owner != module_id:
            raise JobRegistryError(
                "Jobs may be registered only in their provider module namespace.",
                job_id=definition.job_id,
                module_id=module_id,
            )
        existing = self._jobs.get(definition.job_id)
        if existing is not None:
            raise DuplicateJobRegistrationError(
                "The job ID is already registered.",
                job_id=definition.job_id,
                module_id=module_id,
                provider_modules=(existing.module_id, module_id),
            )
        self._jobs[definition.job_id] = JobDescriptor(
            module_id=module_id,
            definition=definition,
            context=context,
            legacy=legacy,
        )
        if definition.schedule is not None:
            logger.info(
                "Module job scheduled",
                extra={
                    "module_id": module_id,
                    "job_id": definition.job_id,
                    "job_phase": "scheduled",
                    "schedule_interval_seconds": definition.schedule.interval_seconds,
                },
            )

    def get(self, job_id: str) -> JobDescriptor:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise UnknownJobError("The requested job is not registered.", job_id=job_id) from exc

    def seal(self) -> None:
        self._sealed = True


class ModuleSchedulerAdapter:
    """An genau ein Modul und seinen ModuleContext gebundener Registrar."""

    def __init__(self, registry: JobRegistry, manifest: ModuleManifestV1) -> None:
        self._registry = registry
        self._manifest = manifest
        self._context: ModuleContext | None = None

    def attach_context(self, context: ModuleContext) -> None:
        if self._context is not None or context.module_id != self._manifest.id:
            raise JobRegistryError(
                "The scheduler adapter cannot be rebound.", module_id=self._manifest.id
            )
        self._context = context

    def register(
        self,
        definition: JobDefinition | str,
        handler: LegacyJobHandler | None = None,
    ) -> None:
        if isinstance(definition, str):
            if handler is None:
                raise TypeError("Compatibility job registration requires a handler.")

            async def invoke(_context: ModuleContext) -> object | None:
                return await handler()

            definition = JobDefinition(job_id=definition, handler=invoke)
        elif handler is not None:
            raise TypeError("JobDefinition registration does not accept a second handler.")
        if "." not in definition.job_id:
            definition = replace(
                definition,
                job_id=f"{self._manifest.id}.{definition.job_id}",
            )
        if self._context is None:
            raise JobRegistryError(
                "The scheduler adapter is not bound to its module context.",
                job_id=definition.job_id,
                module_id=self._manifest.id,
            )
        self._registry.register(
            module_id=self._manifest.id,
            definition=definition,
            context=self._context,
        )


class LegacyJobAdapter:
    """Bindet einen vorhandenen parameterlosen Worker an die neue Registry."""

    def __init__(self, registry: JobRegistry, *, module_id: str) -> None:
        self._registry = registry
        self._module_id = module_id

    def register(
        self,
        *,
        job_id: str,
        handler: Callable[[], Awaitable[object | None]],
        retry: RetryPolicy | None = None,
        timeout_seconds: float | None = None,
        schedule: JobSchedule | None = None,
        allow_concurrent_runs: bool = False,
    ) -> None:
        async def invoke(_context: ModuleContext) -> object | None:
            return await handler()

        definition = JobDefinition(
            job_id=job_id,
            handler=invoke,
            retry=retry or RetryPolicy(),
            timeout_seconds=timeout_seconds,
            schedule=schedule,
            allow_concurrent_runs=allow_concurrent_runs,
        )
        self._registry.register_legacy(module_id=self._module_id, definition=definition)


class _PrometheusJobMetrics:
    runs: "Counter" = MODULE_JOB_RUNS
    failures: "Counter" = MODULE_JOB_FAILURES
    retries: "Counter" = MODULE_JOB_RETRIES
    duration: "Histogram" = MODULE_JOB_DURATION
    last_success: "Gauge" = MODULE_JOB_LAST_SUCCESS


class JobRunner:
    """Führt registrierte Jobs mit Timeout, begrenzten Retries und Telemetrie aus."""

    def __init__(
        self,
        registry: JobRegistry,
        *,
        sleep: Sleep = asyncio.sleep,
        run_id_factory: RunIdFactory = uuid4,
        metrics: object | None = None,
    ) -> None:
        self._registry = registry
        self._sleep = sleep
        self._run_id_factory = run_id_factory
        self._metrics = metrics or _PrometheusJobMetrics()
        self._locks: dict[str, asyncio.Lock] = {}

    async def run(self, job_id: str) -> object | None:
        if not self._registry.sealed:
            raise JobRegistryError("Jobs cannot run before registration is sealed.", job_id=job_id)
        descriptor = self._registry.get(job_id)
        if descriptor.definition.allow_concurrent_runs:
            return await self._execute(descriptor)
        lock = self._locks.setdefault(job_id, asyncio.Lock())
        async with lock:
            return await self._execute(descriptor)

    async def _execute(self, descriptor: JobDescriptor) -> object | None:
        definition = descriptor.definition
        run_id = str(self._run_id_factory())
        started = time.perf_counter()
        for attempt in range(1, definition.retry.max_attempts + 1):
            attempt_started = time.perf_counter()
            fields = _log_fields(descriptor, run_id=run_id, attempt=attempt)
            logger.info("Module job started", extra={**fields, "job_phase": "started"})
            try:
                result = await self._invoke(descriptor)
            except _JobAttemptTimedOut:
                self._metrics.failures.labels(descriptor.module_id, definition.job_id).inc()
                logger.error(
                    "Module job timed out",
                    extra={
                        **fields,
                        "job_phase": "timed_out",
                        "job_duration_ms": _duration_ms(attempt_started),
                        "error_type": "TimeoutError",
                    },
                )
                if attempt == definition.retry.max_attempts:
                    self._record_completion(descriptor, started, result="timed_out")
                    raise JobTimeoutError(
                        "The job exceeded its timeout.",
                        job_id=definition.job_id,
                        module_id=descriptor.module_id,
                        run_id=run_id,
                        attempt=attempt,
                    ) from None
            except Exception as exc:
                self._metrics.failures.labels(descriptor.module_id, definition.job_id).inc()
                logger.error(
                    "Module job attempt failed",
                    extra={
                        **fields,
                        "job_phase": "failed",
                        "job_duration_ms": _duration_ms(attempt_started),
                        "error_type": type(exc).__name__,
                    },
                )
                if attempt == definition.retry.max_attempts:
                    self._record_completion(descriptor, started, result="failed")
                    raise JobExecutionError(
                        "The job failed after its configured attempts.",
                        job_id=definition.job_id,
                        module_id=descriptor.module_id,
                        run_id=run_id,
                        attempt=attempt,
                    ) from exc
            else:
                self._record_completion(descriptor, started, result="succeeded")
                self._metrics.last_success.labels(
                    descriptor.module_id, definition.job_id
                ).set_to_current_time()
                logger.info(
                    "Module job succeeded",
                    extra={
                        **fields,
                        "job_phase": "succeeded",
                        "job_duration_ms": _duration_ms(attempt_started),
                    },
                )
                return result

            delay = definition.retry.delay_after(attempt)
            self._metrics.retries.labels(descriptor.module_id, definition.job_id).inc()
            logger.info(
                "Module job retry scheduled",
                extra={
                    **fields,
                    "job_phase": "retry_scheduled",
                    "retry_delay_seconds": delay,
                },
            )
            if delay:
                await self._sleep(delay)
        raise AssertionError("validated retry policy must execute at least once")

    async def _invoke(self, descriptor: JobDescriptor) -> object | None:
        context = descriptor.context
        if context is None and not descriptor.legacy:
            raise JobRegistryError(
                "The registered module job has no ModuleContext.",
                job_id=descriptor.job_id,
                module_id=descriptor.module_id,
            )
        timeout = descriptor.definition.timeout_seconds
        if timeout is None:
            return await descriptor.definition.handler(context)  # type: ignore[arg-type]
        timeout_scope = asyncio.timeout(timeout)
        try:
            async with timeout_scope:
                return await descriptor.definition.handler(context)  # type: ignore[arg-type]
        except TimeoutError as exc:
            if timeout_scope.expired():
                raise _JobAttemptTimedOut from exc
            raise

    def _record_completion(
        self,
        descriptor: JobDescriptor,
        started: float,
        *,
        result: str,
    ) -> None:
        duration = time.perf_counter() - started
        self._metrics.runs.labels(descriptor.module_id, descriptor.job_id, result).inc()
        self._metrics.duration.labels(
            descriptor.module_id, descriptor.job_id, result
        ).observe(duration)


def _log_fields(descriptor: JobDescriptor, *, run_id: str, attempt: int) -> dict[str, object]:
    return {
        "module_id": descriptor.module_id,
        "job_id": descriptor.job_id,
        "job_run_id": run_id,
        "job_attempt": attempt,
    }


def _duration_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


__all__ = [
    "JobDescriptor",
    "JobRegistry",
    "JobRunner",
    "LegacyJobAdapter",
    "ModuleSchedulerAdapter",
]

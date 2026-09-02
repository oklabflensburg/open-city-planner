import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from app.core.config import get_settings
from app.observability.logging import configure_logging, log_event
from app.observability.metrics import (
    JOB_DURATION,
    JOB_FAILURES,
    JOB_LAST_SUCCESS,
    JOB_RUNS,
    OSM_REPLICATION_LAG,
    OUTBOX_OLDEST_AGE,
    OUTBOX_PENDING,
)

P = ParamSpec("P")
T = TypeVar("T")
logger = logging.getLogger(__name__)


def _metric_state_path(job_name: str) -> Path | None:
    directory = get_settings().observability_textfile_dir
    if not directory:
        return None
    return Path(directory) / f"stadtplaner-{job_name}.json"


def _persist_job_state(
    job_name: str, *, success: bool, duration: float, result: Any = None
) -> None:
    path = _metric_state_path(job_name)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state: dict[str, Any] = {}
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
        state["runs"] = int(state.get("runs", 0)) + 1
        state["failures"] = int(state.get("failures", 0)) + (0 if success else 1)
        state["duration_seconds"] = duration
        state["duration_total_seconds"] = float(state.get("duration_total_seconds", 0)) + duration
        if success:
            state["last_success_timestamp_seconds"] = time.time()
        prom_path = path.with_suffix(".prom")
        prom_temporary = prom_path.with_suffix(f".{os.getpid()}.tmp")
        labels = f'job_name="{job_name}"'
        lines = [
            "# TYPE job_runs_total counter",
            f"job_runs_total{{{labels}}} {state['runs']}",
            "# TYPE job_failures_total counter",
            f"job_failures_total{{{labels}}} {state['failures']}",
            "# TYPE job_duration_seconds histogram",
            f'job_duration_seconds_bucket{{{labels},le="+Inf"}} {state["runs"]}',
            f"job_duration_seconds_count{{{labels}}} {state['runs']}",
            f"job_duration_seconds_sum{{{labels}}} {state['duration_total_seconds']}",
            "# TYPE job_last_success_timestamp_seconds gauge",
            (
                f"job_last_success_timestamp_seconds{{{labels}}} "
                f"{float(state.get('last_success_timestamp_seconds', 0))}"
            ),
        ]
        outbox_type = {
            "email_outbox": "email",
            "polygon_outbox": "polygon",
        }.get(job_name)
        if outbox_type and isinstance(result, dict):
            processed = int(
                result.get("sent", 0)
                or result.get("published", 0) + result.get("dry_run", 0)
                or result.get("processed", 0)
            )
            failed = int(result.get("dead_letter", result.get("failed", 0)))
            retried = int(result.get("retried", 0))
            state["outbox_processed"] = int(state.get("outbox_processed", 0)) + processed
            state["outbox_failed"] = int(state.get("outbox_failed", 0)) + failed
            state["outbox_retry"] = int(state.get("outbox_retry", 0)) + retried
            outbox_labels = f'outbox_type="{outbox_type}"'
            lines.extend(
                (
                    "# TYPE outbox_pending gauge",
                    (
                        f"outbox_pending{{{outbox_labels}}} "
                        f"{OUTBOX_PENDING.labels(outbox_type)._value.get()}"
                    ),
                    "# TYPE outbox_oldest_age_seconds gauge",
                    (
                        f"outbox_oldest_age_seconds{{{outbox_labels}}} "
                        f"{OUTBOX_OLDEST_AGE.labels(outbox_type)._value.get()}"
                    ),
                    "# TYPE outbox_processed_total counter",
                    f"outbox_processed_total{{{outbox_labels}}} {state['outbox_processed']}",
                    "# TYPE outbox_failed_total counter",
                    f"outbox_failed_total{{{outbox_labels}}} {state['outbox_failed']}",
                    "# TYPE outbox_retry_total counter",
                    f"outbox_retry_total{{{outbox_labels}}} {state['outbox_retry']}",
                )
            )
        if job_name == "osm_replication":
            lines.extend(
                (
                    "# TYPE osm_replication_lag_seconds gauge",
                    f"osm_replication_lag_seconds {OSM_REPLICATION_LAG._value.get()}",
                )
            )
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, path)
        lines.append("")
        prom_temporary.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )
        os.replace(prom_temporary, prom_path)
    except (OSError, ValueError, TypeError):
        logger.exception("job_metric_state_write_failed", extra={"job_name": job_name})


def observed_job(job_name: str) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorator(function: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(function)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            settings = get_settings()
            configure_logging(
                level=settings.log_level,
                service=f"stadtplaner-job-{job_name}",
                environment=settings.app_environment,
                release_sha=settings.release_sha,
                json_logs=settings.log_format == "json",
            )
            started = time.perf_counter()
            JOB_RUNS.labels(job_name).inc()
            try:
                result = await function(*args, **kwargs)
            except BaseException:
                duration = time.perf_counter() - started
                JOB_FAILURES.labels(job_name).inc()
                JOB_DURATION.labels(job_name).observe(duration)
                _persist_job_state(job_name, success=False, duration=duration)
                log_event(logger, logging.ERROR, "job_failed", job_name=job_name, duration_seconds=duration)
                raise
            duration = time.perf_counter() - started
            JOB_DURATION.labels(job_name).observe(duration)
            JOB_LAST_SUCCESS.labels(job_name).set_to_current_time()
            _persist_job_state(job_name, success=True, duration=duration, result=result)
            log_event(
                logger,
                logging.INFO,
                "job_completed",
                job_name=job_name,
                duration_seconds=duration,
                result=result,
            )
            return result

        return wrapped

    return decorator

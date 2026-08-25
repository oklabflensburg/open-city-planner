"""SQLAlchemy-Adapter und Dispatcher für die zentrale transaktionale Outbox."""

import logging
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from opentelemetry import trace
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain_event_outbox import DomainEventOutbox, EventDelivery
from app.observability.context import request_id
from app.observability.logging import trace_context
from app.observability.metrics import (
    EVENT_DEAD_LETTER,
    EVENT_DISPATCH,
    EVENT_DISPATCH_FAILURES,
    EVENT_HANDLER_DURATION,
    EVENT_OUTBOX_OLDEST_AGE,
    EVENT_OUTBOX_PENDING,
)
from app.platform.events.bus import EventSubscription, InProcessEventBus
from app.platform.modules.sdk import (
    DomainEvent,
    EventEnvelope,
    EventHandler,
    SerializableDomainEvent,
    event_envelope,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
_TERMINAL_DELIVERY_STATUSES = ("SUCCEEDED", "DEAD_LETTER")
_MODULE_ID = re.compile(r"^[a-z][a-z0-9-]{0,79}$")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    delays_seconds: tuple[int, ...] = (30, 120, 600, 3600)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("Retry max_attempts must be positive.")
        if not self.delays_seconds or any(delay < 0 for delay in self.delays_seconds):
            raise ValueError("Retry delays must contain non-negative seconds.")

    def delay_after(self, attempt_count: int) -> timedelta:
        index = min(max(attempt_count - 1, 0), len(self.delays_seconds) - 1)
        return timedelta(seconds=self.delays_seconds[index])


class HostEventBusAdapter:
    """An ein Producer-/Consumer-Modul gebundener Public-SDK-Adapter."""

    def __init__(self, bus: InProcessEventBus, *, module_id: str) -> None:
        if not _MODULE_ID.fullmatch(module_id):
            raise ValueError("Module IDs must be stable lowercase identifiers.")
        self._bus = bus
        self._module_id = module_id

    async def publish(
        self, event: DomainEvent | SerializableDomainEvent | EventEnvelope
    ) -> None:
        await self._bus.dispatch(self._envelope(event))

    async def publish_after_commit(
        self,
        event: DomainEvent | SerializableDomainEvent | EventEnvelope,
        *,
        session: AsyncSession,
    ) -> EventEnvelope:
        envelope = self._envelope(event)
        session.add(
            DomainEventOutbox(
                event_id=envelope.event_id,
                event_name=envelope.event_name,
                event_version=envelope.event_version,
                producer_module=self._module_id,
                payload=_plain_json(envelope.payload),
                event_metadata={
                    "correlation_id": envelope.correlation_id,
                    "causation_id": envelope.causation_id,
                    "trace_context": dict(envelope.trace_context),
                },
                occurred_at=envelope.occurred_at,
                available_at=_now(),
            )
        )
        _log(envelope, phase="queued")
        return envelope

    def subscribe(
        self,
        event_name: str,
        *,
        handler_id: str,
        versions: frozenset[int],
        handler: EventHandler,
    ) -> None:
        if not handler_id.startswith(f"{self._module_id}."):
            raise ValueError("Handler IDs must be namespaced by the subscribing module.")
        self._bus.subscribe(
            event_name,
            handler_id=handler_id,
            versions=versions,
            handler=handler,
        )

    def _envelope(
        self, event: DomainEvent | SerializableDomainEvent | EventEnvelope
    ) -> EventEnvelope:
        envelope = event if isinstance(event, EventEnvelope) else event_envelope(event)
        if not envelope.event_name.startswith(f"{self._module_id}."):
            raise ValueError("Published event names must be namespaced by the producer module.")
        if envelope.producer_module not in (None, self._module_id):
            raise ValueError("The event envelope is bound to a different producer module.")
        trace_id, span_id = trace_context()
        propagated_trace = dict(envelope.trace_context)
        if trace_id:
            propagated_trace.setdefault("trace_id", trace_id)
        if span_id:
            propagated_trace.setdefault("span_id", span_id)
        return replace(
            envelope,
            producer_module=self._module_id,
            correlation_id=envelope.correlation_id or request_id(),
            trace_context=propagated_trace,
        )


class OutboxDispatcher:
    """Kleiner, manuell/timer-gesteuert aufrufbarer at-least-once Dispatcher."""

    def __init__(
        self,
        bus: InProcessEventBus,
        *,
        worker_id: str,
        retry_policy: RetryPolicy | None = None,
        lock_timeout: timedelta = timedelta(minutes=10),
    ) -> None:
        if not worker_id.strip():
            raise ValueError("A stable non-empty worker ID is required.")
        self._bus = bus
        if len(worker_id) > 160:
            raise ValueError("Worker IDs must not exceed 160 characters.")
        if lock_timeout <= timedelta(0):
            raise ValueError("The lock timeout must be positive.")
        self._worker_id = worker_id
        self._retry_policy = retry_policy or RetryPolicy()
        self._lock_timeout = lock_timeout

    async def run_once(self, session: AsyncSession, *, limit: int = 50) -> dict[str, int]:
        result = {"processed": 0, "retried": 0, "dead_lettered": 0, "ignored": 0}
        result["ignored"] = await self._initialize_deliveries(session, limit=limit)
        await self._recover_stale_claims(session)
        for _ in range(limit):
            claimed = await self._claim_delivery(session)
            if claimed is None:
                break
            delivery_id, subscription, envelope = claimed
            started = time.perf_counter()
            outcome = "success"
            try:
                with tracer.start_as_current_span(
                    "domain_event.dispatch",
                    attributes={
                        "event.name": envelope.event_name,
                        "event.version": envelope.event_version,
                        "event.handler": subscription.handler_id,
                    },
                ) as span:
                    span.set_attribute(
                        "event.attempt",
                        await self._attempt_count(session, delivery_id),
                    )
                    await self._bus.dispatch_to(subscription, envelope)
            except Exception as exc:  # noqa: BLE001 - failures are persisted for retry
                outcome = "failure"
                dead_lettered = await self._mark_failure(session, delivery_id, envelope, exc)
                result["dead_lettered" if dead_lettered else "retried"] += 1
            else:
                await self._mark_success(session, delivery_id, envelope)
                result["processed"] += 1
            finally:
                EVENT_HANDLER_DURATION.labels(
                    envelope.event_name,
                    subscription.handler_id,
                    outcome,
                ).observe(time.perf_counter() - started)
        await update_domain_event_metrics(session)
        return result

    async def _initialize_deliveries(self, session: AsyncSession, *, limit: int) -> int:
        events = (
            await session.scalars(
                select(DomainEventOutbox)
                .where(
                    DomainEventOutbox.processed_at.is_(None),
                    DomainEventOutbox.deliveries_created_at.is_(None),
                    DomainEventOutbox.available_at <= _now(),
                )
                .order_by(DomainEventOutbox.available_at, DomainEventOutbox.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        ignored = 0
        for event in events:
            named = tuple(
                subscription
                for subscription in self._bus.subscriptions
                if subscription.event_name == event.event_name
            )
            for subscription in named:
                supported = event.event_version in subscription.versions
                session.add(
                    EventDelivery(
                        outbox_id=event.id,
                        event_id=event.event_id,
                        handler_id=subscription.handler_id,
                        status="PENDING" if supported else "DEAD_LETTER",
                        available_at=max(event.available_at, _now()),
                        dead_lettered_at=None if supported else _now(),
                        last_error=(
                            None
                            if supported
                            else f"Unsupported event version {event.event_version}."
                        ),
                    )
                )
                if not supported:
                    EVENT_DEAD_LETTER.labels(event.event_name, subscription.handler_id).inc()
                    _log_row(
                        event,
                        phase="dead_lettered",
                        handler_id=subscription.handler_id,
                        attempt=0,
                    )
            event.deliveries_created_at = _now()
            if not named:
                event.processed_at = _now()
                ignored += 1
            elif not any(event.event_version in item.versions for item in named):
                event.processed_at = _now()
        await session.commit()
        return ignored

    async def _recover_stale_claims(self, session: AsyncSession) -> None:
        stale_before = _now() - self._lock_timeout
        await session.execute(
            update(EventDelivery)
            .where(
                EventDelivery.status == "PROCESSING",
                or_(EventDelivery.locked_at.is_(None), EventDelivery.locked_at < stale_before),
            )
            .values(status="PENDING", locked_at=None, locked_by=None)
        )
        await session.commit()

    async def _claim_delivery(
        self,
        session: AsyncSession,
    ) -> tuple[UUID, EventSubscription, EventEnvelope] | None:
        row = (
            await session.execute(
                select(EventDelivery, DomainEventOutbox)
                .join(DomainEventOutbox, DomainEventOutbox.id == EventDelivery.outbox_id)
                .where(
                    EventDelivery.status == "PENDING",
                    EventDelivery.available_at <= _now(),
                )
                .order_by(EventDelivery.available_at, DomainEventOutbox.created_at)
                .with_for_update(skip_locked=True, of=EventDelivery)
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            return None
        delivery, event = row
        subscription = self._bus.subscription(delivery.handler_id)
        if subscription is None:
            delivery.status = "DEAD_LETTER"
            delivery.dead_lettered_at = _now()
            delivery.last_error = "The registered handler is not available in this worker."
            await session.flush()
            await self._complete_event_if_terminal(session, delivery.outbox_id)
            await session.commit()
            EVENT_DEAD_LETTER.labels(event.event_name, delivery.handler_id).inc()
            _log_row(
                event,
                phase="dead_lettered",
                handler_id=delivery.handler_id,
                attempt=delivery.attempt_count,
            )
            return None
        delivery.status = "PROCESSING"
        delivery.attempt_count += 1
        delivery.last_attempt_at = _now()
        delivery.locked_at = _now()
        delivery.locked_by = self._worker_id
        envelope = _envelope_from_row(event)
        attempt = delivery.attempt_count
        delivery_id = delivery.id
        await session.commit()
        _log(envelope, phase="claimed", handler_id=subscription.handler_id, attempt=attempt)
        _log(
            envelope,
            phase="dispatch_started",
            handler_id=subscription.handler_id,
            attempt=attempt,
        )
        return delivery_id, subscription, envelope

    async def _attempt_count(self, session: AsyncSession, delivery_id: UUID) -> int:
        return int(
            await session.scalar(
                select(EventDelivery.attempt_count).where(EventDelivery.id == delivery_id)
            )
            or 0
        )

    async def _mark_success(
        self,
        session: AsyncSession,
        delivery_id: UUID,
        envelope: EventEnvelope,
    ) -> None:
        delivery = await session.get(EventDelivery, delivery_id, with_for_update=True)
        if delivery is None or delivery.status != "PROCESSING":
            return
        delivery.status = "SUCCEEDED"
        delivery.processed_at = _now()
        delivery.locked_at = None
        delivery.locked_by = None
        delivery.last_error = None
        await session.flush()
        await self._complete_event_if_terminal(session, delivery.outbox_id)
        await session.commit()
        EVENT_DISPATCH.labels(envelope.event_name, delivery.handler_id, "success").inc()
        _log(
            envelope,
            phase="dispatch_succeeded",
            handler_id=delivery.handler_id,
            attempt=delivery.attempt_count,
        )

    async def _mark_failure(
        self,
        session: AsyncSession,
        delivery_id: UUID,
        envelope: EventEnvelope,
        error: Exception,
    ) -> bool:
        await session.rollback()
        delivery = await session.get(EventDelivery, delivery_id, with_for_update=True)
        if delivery is None:
            return False
        delivery.locked_at = None
        delivery.locked_by = None
        delivery.last_error = f"{type(error).__name__}: {error}"[:2000]
        dead_lettered = delivery.attempt_count >= self._retry_policy.max_attempts
        if dead_lettered:
            delivery.status = "DEAD_LETTER"
            delivery.dead_lettered_at = _now()
            await session.flush()
            await self._complete_event_if_terminal(session, delivery.outbox_id)
        else:
            delivery.status = "PENDING"
            delivery.available_at = _now() + self._retry_policy.delay_after(delivery.attempt_count)
        await session.commit()
        EVENT_DISPATCH.labels(envelope.event_name, delivery.handler_id, "failure").inc()
        EVENT_DISPATCH_FAILURES.labels(envelope.event_name, delivery.handler_id).inc()
        _log(
            envelope,
            phase="dispatch_failed",
            handler_id=delivery.handler_id,
            attempt=delivery.attempt_count,
            error_type=type(error).__name__,
        )
        phase = "dead_lettered" if dead_lettered else "retry_scheduled"
        if dead_lettered:
            EVENT_DEAD_LETTER.labels(envelope.event_name, delivery.handler_id).inc()
        _log(
            envelope,
            phase=phase,
            handler_id=delivery.handler_id,
            attempt=delivery.attempt_count,
            error_type=type(error).__name__,
        )
        return dead_lettered

    async def _complete_event_if_terminal(self, session: AsyncSession, outbox_id: UUID) -> None:
        incomplete = await session.scalar(
            select(func.count(EventDelivery.id)).where(
                EventDelivery.outbox_id == outbox_id,
                EventDelivery.status.not_in(_TERMINAL_DELIVERY_STATUSES),
            )
        )
        if not incomplete:
            event = await session.get(DomainEventOutbox, outbox_id, with_for_update=True)
            if event is not None:
                event.processed_at = _now()


async def update_domain_event_metrics(session: AsyncSession) -> None:
    try:
        pending = await session.scalar(
            select(func.count(DomainEventOutbox.id)).where(
                DomainEventOutbox.processed_at.is_(None)
            )
        )
        oldest = await session.scalar(
            select(func.min(DomainEventOutbox.created_at)).where(
                DomainEventOutbox.processed_at.is_(None)
            )
        )
    except Exception as exc:  # noqa: BLE001 - telemetry must not break dispatch
        logger.warning(
            "domain_event_metrics_collection_failed",
            extra={"error_type": type(exc).__name__},
        )
        return
    EVENT_OUTBOX_PENDING.set(int(pending or 0))
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    EVENT_OUTBOX_OLDEST_AGE.set(
        max(0.0, (_now() - oldest).total_seconds()) if oldest is not None else 0.0
    )


async def delete_processed_events_before(session: AsyncSession, cutoff: datetime) -> int:
    """Expliziter Retention-Hook; Scheduling bleibt #100 vorbehalten."""

    rows = (
        await session.scalars(
            select(DomainEventOutbox).where(
                DomainEventOutbox.processed_at.is_not(None),
                DomainEventOutbox.processed_at < cutoff,
            )
        )
    ).all()
    for row in rows:
        await session.delete(row)
    return len(rows)


def _envelope_from_row(row: DomainEventOutbox) -> EventEnvelope:
    metadata = row.event_metadata or {}
    return EventEnvelope(
        event_id=row.event_id,
        event_name=row.event_name,
        event_version=row.event_version,
        occurred_at=row.occurred_at,
        payload=row.payload,
        correlation_id=metadata.get("correlation_id"),
        causation_id=metadata.get("causation_id"),
        trace_context=metadata.get("trace_context") or {},
        producer_module=row.producer_module,
    )


def _plain_json(value: object) -> dict:
    serialized = _plain_json_value(value)
    if not isinstance(serialized, dict):
        raise TypeError("Event payloads must serialize to JSON objects.")
    return serialized


def _plain_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_json_value(item) for item in value]
    return value


def _now() -> datetime:
    return datetime.now(UTC)


def _log(
    envelope: EventEnvelope,
    *,
    phase: str,
    handler_id: str | None = None,
    attempt: int | None = None,
    error_type: str | None = None,
) -> None:
    logger.info(
        "domain_event_%s",
        phase,
        extra={
            "event_id": str(envelope.event_id),
            "event_name": envelope.event_name,
            "event_version": envelope.event_version,
            "producer_module": envelope.producer_module,
            "handler_id": handler_id,
            "attempt": attempt,
            "correlation_id": envelope.correlation_id,
            "event_phase": phase,
            "error_type": error_type,
        },
    )


def _log_row(
    row: DomainEventOutbox,
    *,
    phase: str,
    handler_id: str,
    attempt: int,
) -> None:
    _log(
        _envelope_from_row(row),
        phase=phase,
        handler_id=handler_id,
        attempt=attempt,
    )

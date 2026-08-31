import ast
import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import Column, MetaData, String, Table, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.db.base import Base
from app.models.domain_event_outbox import DomainEventOutbox, EventDelivery
from app.platform.events import (
    DuplicateEventHandlerError,
    EventDispatchError,
    HostEventBusAdapter,
    InProcessEventBus,
    OutboxDispatcher,
    RetryPolicy,
    UnsupportedEventVersionError,
)
from app.platform.modules.context import ModuleContextFactory
from app.platform.modules.contracts import ModuleRegistrationContext
from app.platform.modules.manifest import parse_manifest
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    EventEnvelope,
    JsonValue,
    OsmPostprocessingCompleted,
    event_envelope,
)
from app.services.osm_event_publisher import enqueue_osm_postprocessing_completed
from app.services.polygon_event_handlers import register_polygon_event_handlers
from app.services.polygon_event_publisher import enqueue_polygon_event
from app.services.polygon_events import PolygonCreated
from tests.fixtures.event_subscriber_module import DEFINITION as SUBSCRIBER_DEFINITION
from tests.test_module_runtime import FakeDiscovery


@dataclass(frozen=True, slots=True)
class ExampleCreated:
    value: str
    event_name: ClassVar[str] = "example.created"
    event_version: ClassVar[int] = 1

    def to_payload(self) -> dict[str, JsonValue]:
        return {"value": self.value}


@dataclass(frozen=True, slots=True)
class LegacyEvent:
    event_type: str = "legacy.created"
    event_version: int = 1


def test_event_envelope_has_stable_metadata_and_json_payload() -> None:
    event_id = uuid.uuid4()
    occurred_at = datetime(2026, 8, 25, 18, 0, tzinfo=UTC)

    envelope = event_envelope(
        ExampleCreated("ok"),
        event_id=event_id,
        occurred_at=occurred_at,
        correlation_id="request-1",
        causation_id="cause-1",
        trace_context={"trace_id": "trace-1"},
    )

    assert envelope.event_id == event_id
    assert envelope.event_name == "example.created"
    assert envelope.event_version == 1
    assert envelope.occurred_at == occurred_at
    assert envelope.correlation_id == "request-1"
    assert envelope.causation_id == "cause-1"
    assert envelope.trace_context == {"trace_id": "trace-1"}
    assert envelope.payload == {"value": "ok"}


def test_sdk_1_0_domain_event_identity_remains_compatible() -> None:
    envelope = event_envelope(LegacyEvent())

    assert envelope.event_name == "legacy.created"
    assert envelope.event_version == 1
    assert envelope.payload == {}


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("event_name", "ExampleCreated", ValueError),
        ("event_version", 0, ValueError),
        ("occurred_at", datetime(2026, 8, 25, tzinfo=UTC).replace(tzinfo=None), ValueError),
        ("payload", {"value": uuid.uuid4()}, TypeError),
        ("payload", {"value": float("nan")}, ValueError),
        ("trace_context", {"trace_id": 1}, TypeError),
    ],
)
def test_event_envelope_rejects_invalid_contract_values(
    field: str, value: object, error: type[Exception]
) -> None:
    values = {
        "event_id": uuid.uuid4(),
        "event_name": "example.created",
        "event_version": 1,
        "occurred_at": datetime.now(UTC),
        "payload": {"value": "ok"},
        "trace_context": {},
    }
    values[field] = value
    with pytest.raises(error):
        EventEnvelope(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bus_dispatches_sync_and_async_handlers_in_registration_order() -> None:
    bus = InProcessEventBus()
    order: list[str] = []

    def first(_event: EventEnvelope) -> None:
        order.append("first")

    async def second(_event: EventEnvelope) -> None:
        order.append("second")

    bus.subscribe(
        "example.created",
        handler_id="first.example-created",
        versions=frozenset({1}),
        handler=first,
    )
    bus.subscribe(
        "example.created",
        handler_id="second.example-created",
        versions=frozenset({1}),
        handler=second,
    )

    await bus.dispatch(event_envelope(ExampleCreated("ok")))

    assert order == ["first", "second"]


def test_bus_rejects_duplicate_handler_id_and_unsupported_version() -> None:
    bus = InProcessEventBus()
    bus.subscribe(
        "example.created",
        handler_id="consumer.example-created",
        versions=frozenset({1}),
        handler=lambda _event: None,
    )
    with pytest.raises(DuplicateEventHandlerError):
        bus.subscribe(
            "other.created",
            handler_id="consumer.example-created",
            versions=frozenset({1}),
            handler=lambda _event: None,
        )
    with pytest.raises(UnsupportedEventVersionError):
        bus.subscriptions_for("example.created", 2)
    assert bus.subscriptions_for("unknown.created", 1) == ()


@pytest.mark.asyncio
async def test_direct_dispatch_propagates_handler_context() -> None:
    bus = InProcessEventBus()

    async def failing(_event: EventEnvelope) -> None:
        raise RuntimeError("expected")

    bus.subscribe(
        "example.created",
        handler_id="consumer.failing",
        versions=frozenset({1}),
        handler=failing,
    )
    envelope = event_envelope(ExampleCreated("ok"))

    with pytest.raises(EventDispatchError) as captured:
        await bus.dispatch(envelope)

    assert captured.value.event_id == envelope.event_id
    assert captured.value.event_name == envelope.event_name
    assert captured.value.handler_id == "consumer.failing"


@dataclass(frozen=True, slots=True)
class PostgresFixture:
    sessions: async_sessionmaker[AsyncSession]
    facts: Table


@pytest_asyncio.fixture
async def postgres_events() -> AsyncIterator[PostgresFixture]:
    url = make_url(get_settings().database_url).set(database="postgres")
    schema = f"test_domain_events_{uuid.uuid4().hex}"
    admin = create_async_engine(url)
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    except (ConnectionError, DBAPIError, OSError, OperationalError) as exc:
        await admin.dispose()
        pytest.skip(f"PostgreSQL test database is unavailable: {type(exc).__name__}")

    engine = create_async_engine(
        url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    metadata = MetaData()
    facts = Table(
        "event_test_facts",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("value", String(80), nullable=False),
    )
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[DomainEventOutbox.__table__, EventDelivery.__table__],
            )
        )
        await connection.run_sync(metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield PostgresFixture(sessions=sessions, facts=facts)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.mark.asyncio
async def test_transactional_publish_is_invisible_before_commit_and_removed_by_rollback(
    postgres_events: PostgresFixture,
) -> None:
    bus = InProcessEventBus()
    calls: list[uuid.UUID] = []
    bus.subscribe(
        "example.created",
        handler_id="consumer.transaction-test",
        versions=frozenset({1}),
        handler=lambda envelope: calls.append(envelope.event_id),
    )
    adapter = HostEventBusAdapter(bus, module_id="example")
    fact_id = str(uuid.uuid4())
    async with postgres_events.sessions() as writer, writer.begin():
        await writer.execute(insert(postgres_events.facts).values(id=fact_id, value="committed"))
        await adapter.publish_after_commit(ExampleCreated("committed"), session=writer)
        async with postgres_events.sessions() as observer:
            assert await observer.scalar(select(func.count(DomainEventOutbox.id))) == 0
            assert await observer.scalar(select(func.count(postgres_events.facts.c.id))) == 0
            assert calls == []

    async with postgres_events.sessions() as observer:
        assert await observer.scalar(select(func.count(DomainEventOutbox.id))) == 1
        assert await observer.scalar(select(func.count(postgres_events.facts.c.id))) == 1
        assert calls == []

    async with postgres_events.sessions() as writer:
        await writer.execute(
            insert(postgres_events.facts).values(id=str(uuid.uuid4()), value="rolled-back")
        )
        await adapter.publish_after_commit(ExampleCreated("rolled-back"), session=writer)
        await writer.rollback()
    async with postgres_events.sessions() as observer:
        assert await observer.scalar(select(func.count(DomainEventOutbox.id))) == 1
        assert await observer.scalar(select(func.count(postgres_events.facts.c.id))) == 1


@pytest.mark.asyncio
async def test_osm_completion_event_shares_commit_and_rollback_boundary(
    postgres_events: PostgresFixture,
) -> None:
    event = OsmPostprocessingCompleted(
        sequence=123,
        osm_timestamp=datetime(2026, 8, 31, tzinfo=UTC),
        inserted=2,
        updated=3,
        deleted=1,
    )
    async with postgres_events.sessions() as session:
        await session.execute(
            insert(postgres_events.facts).values(id=str(uuid.uuid4()), value="osm-committed")
        )
        await enqueue_osm_postprocessing_completed(session, event)
        await session.commit()
    async with postgres_events.sessions() as observer:
        row = await observer.scalar(
            select(DomainEventOutbox).where(
                DomainEventOutbox.event_name == "osm.postprocessing-completed"
            )
        )
        assert row is not None
        assert row.payload["sequence"] == 123

    async with postgres_events.sessions() as session:
        await enqueue_osm_postprocessing_completed(session, event)
        await session.rollback()
    async with postgres_events.sessions() as observer:
        assert await observer.scalar(
            select(func.count(DomainEventOutbox.id)).where(
                DomainEventOutbox.event_name == "osm.postprocessing-completed"
            )
        ) == 1


@pytest.mark.asyncio
async def test_dispatcher_retries_only_failed_handler_and_preserves_metadata(
    postgres_events: PostgresFixture,
) -> None:
    bus = InProcessEventBus()
    calls: list[tuple[str, str | None, str | None]] = []
    fail_second = True

    async def first(envelope: EventEnvelope) -> None:
        calls.append(("first", envelope.correlation_id, envelope.causation_id))

    async def second(envelope: EventEnvelope) -> None:
        calls.append(("second", envelope.correlation_id, envelope.causation_id))
        if fail_second:
            raise RuntimeError("retry me")

    bus.subscribe(
        "example.created",
        handler_id="consumer.first",
        versions=frozenset({1}),
        handler=first,
    )
    bus.subscribe(
        "example.created",
        handler_id="consumer.second",
        versions=frozenset({1}),
        handler=second,
    )
    adapter = HostEventBusAdapter(bus, module_id="example")
    envelope = event_envelope(
        ExampleCreated("ok"), correlation_id="request-1", causation_id="cause-1"
    )
    async with postgres_events.sessions() as session:
        await session.execute(
            insert(postgres_events.facts).values(id=str(uuid.uuid4()), value="survives")
        )
        await adapter.publish_after_commit(envelope, session=session)
        await session.commit()
        dispatcher = OutboxDispatcher(
            bus,
            worker_id="worker-1",
            retry_policy=RetryPolicy(max_attempts=3, delays_seconds=(3600,)),
        )
        result = await dispatcher.run_once(session)

    assert result == {"processed": 1, "retried": 1, "dead_lettered": 0, "ignored": 0}
    async with postgres_events.sessions() as observer:
        assert await observer.scalar(select(func.count(postgres_events.facts.c.id))) == 1
    assert calls == [
        ("first", "request-1", "cause-1"),
        ("second", "request-1", "cause-1"),
    ]

    fail_second = False
    async with postgres_events.sessions() as session:
        await session.execute(
            update(EventDelivery)
            .where(EventDelivery.handler_id == "consumer.second")
            .values(available_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
        result = await dispatcher.run_once(session)
        deliveries = (
            await session.scalars(select(EventDelivery).order_by(EventDelivery.handler_id))
        ).all()
        outbox = await session.scalar(select(DomainEventOutbox))

    assert result["processed"] == 1
    assert calls == [
        ("first", "request-1", "cause-1"),
        ("second", "request-1", "cause-1"),
        ("second", "request-1", "cause-1"),
    ]
    assert [(item.handler_id, item.status, item.attempt_count) for item in deliveries] == [
        ("consumer.first", "SUCCEEDED", 1),
        ("consumer.second", "SUCCEEDED", 2),
    ]
    assert outbox is not None and outbox.processed_at is not None

    async with postgres_events.sessions() as session:
        await dispatcher.run_once(session)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_dispatcher_dead_letters_after_max_attempts(
    postgres_events: PostgresFixture,
) -> None:
    bus = InProcessEventBus()

    async def failing(_envelope: EventEnvelope) -> None:
        raise RuntimeError("permanent")

    bus.subscribe(
        "example.created",
        handler_id="consumer.permanent-failure",
        versions=frozenset({1}),
        handler=failing,
    )
    adapter = HostEventBusAdapter(bus, module_id="example")
    dispatcher = OutboxDispatcher(
        bus,
        worker_id="worker-dead-letter",
        retry_policy=RetryPolicy(max_attempts=2, delays_seconds=(0,)),
    )
    async with postgres_events.sessions() as session:
        await adapter.publish_after_commit(ExampleCreated("failed"), session=session)
        await session.commit()
        result = await dispatcher.run_once(session)
        delivery = await session.scalar(select(EventDelivery))

    assert result["retried"] == 1
    assert result["dead_lettered"] == 1
    assert delivery is not None
    assert delivery.status == "DEAD_LETTER"
    assert delivery.attempt_count == 2
    assert delivery.dead_lettered_at is not None
    assert (
        delivery.last_error
        == 'EventDispatchError: Handler "consumer.permanent-failure" failed for event "example.created" version 1 ('
        + str(delivery.event_id)
        + ")."
    )


@pytest.mark.asyncio
async def test_dispatcher_completes_unknown_events_and_dead_letters_unsupported_versions(
    postgres_events: PostgresFixture,
) -> None:
    bus = InProcessEventBus()
    bus.subscribe(
        "example.created",
        handler_id="consumer.version-one",
        versions=frozenset({1}),
        handler=lambda _event: None,
    )
    adapter = HostEventBusAdapter(bus, module_id="example")
    unknown_adapter = HostEventBusAdapter(bus, module_id="unknown")
    unsupported = EventEnvelope(
        event_id=uuid.uuid4(),
        event_name="example.created",
        event_version=2,
        occurred_at=datetime.now(UTC),
        payload={"value": "new"},
    )
    async with postgres_events.sessions() as session:
        await unknown_adapter.publish_after_commit(
            LegacyEvent("unknown.created"), session=session
        )
        await adapter.publish_after_commit(unsupported, session=session)
        await session.commit()
        result = await OutboxDispatcher(bus, worker_id="worker-versions").run_once(session)
        rows = (
            await session.scalars(
                select(DomainEventOutbox).order_by(DomainEventOutbox.event_name)
            )
        ).all()
        delivery = await session.scalar(select(EventDelivery))

    assert result["ignored"] == 1
    assert all(row.processed_at is not None for row in rows)
    assert delivery is not None
    assert delivery.status == "DEAD_LETTER"
    assert delivery.attempt_count == 0
    assert delivery.last_error == "Unsupported event version 2."


@pytest.mark.asyncio
async def test_postgres_skip_locked_prevents_double_claim(
    postgres_events: PostgresFixture,
) -> None:
    event_id = uuid.uuid4()
    now = datetime.now(UTC)
    async with postgres_events.sessions() as setup:
        event = DomainEventOutbox(
            event_id=event_id,
            event_name="example.created",
            event_version=1,
            producer_module="example",
            payload={"value": "ok"},
            event_metadata={},
            occurred_at=now,
            available_at=now,
            deliveries_created_at=now,
        )
        setup.add(event)
        await setup.flush()
        setup.add(
            EventDelivery(
                outbox_id=event.id,
                event_id=event_id,
                handler_id="consumer.locked",
                status="PENDING",
                available_at=now,
            )
        )
        await setup.commit()

    statement = (
        select(EventDelivery)
        .where(EventDelivery.status == "PENDING")
        .with_for_update(skip_locked=True)
    )
    async with postgres_events.sessions() as first, postgres_events.sessions() as second:
        first_row = await first.scalar(statement)
        second_row = await second.scalar(statement)
        assert first_row is not None
        assert second_row is None
        await first.rollback()
        await second.rollback()


@pytest.mark.asyncio
async def test_two_dispatchers_cannot_claim_the_same_delivery(
    postgres_events: PostgresFixture,
) -> None:
    event_id = uuid.uuid4()
    now = datetime.now(UTC)
    bus = InProcessEventBus()
    bus.subscribe(
        "example.created",
        handler_id="consumer.concurrent",
        versions=frozenset({1}),
        handler=lambda _event: None,
    )
    async with postgres_events.sessions() as setup:
        event = DomainEventOutbox(
            event_id=event_id,
            event_name="example.created",
            event_version=1,
            producer_module="example",
            payload={"value": "ok"},
            event_metadata={},
            occurred_at=now,
            available_at=now,
            deliveries_created_at=now,
        )
        setup.add(event)
        await setup.flush()
        setup.add(
            EventDelivery(
                outbox_id=event.id,
                event_id=event_id,
                handler_id="consumer.concurrent",
                status="PENDING",
                available_at=now,
            )
        )
        await setup.commit()

    first_dispatcher = OutboxDispatcher(bus, worker_id="worker-concurrent-1")
    second_dispatcher = OutboxDispatcher(bus, worker_id="worker-concurrent-2")
    async with postgres_events.sessions() as first, postgres_events.sessions() as second:
        claims = await asyncio.gather(
            first_dispatcher._claim_delivery(first),
            second_dispatcher._claim_delivery(second),
        )

    assert sum(claim is not None for claim in claims) == 1


@pytest.mark.asyncio
async def test_dispatcher_recovers_stale_processing_lock(
    postgres_events: PostgresFixture,
) -> None:
    calls: list[uuid.UUID] = []
    bus = InProcessEventBus()
    bus.subscribe(
        "example.created",
        handler_id="consumer.stale-lock",
        versions=frozenset({1}),
        handler=lambda envelope: calls.append(envelope.event_id),
    )
    event_id = uuid.uuid4()
    now = datetime.now(UTC)
    async with postgres_events.sessions() as setup:
        event = DomainEventOutbox(
            event_id=event_id,
            event_name="example.created",
            event_version=1,
            producer_module="example",
            payload={"value": "ok"},
            event_metadata={},
            occurred_at=now,
            available_at=now,
            deliveries_created_at=now,
        )
        setup.add(event)
        await setup.flush()
        setup.add(
            EventDelivery(
                outbox_id=event.id,
                event_id=event_id,
                handler_id="consumer.stale-lock",
                status="PROCESSING",
                attempt_count=1,
                available_at=now,
                locked_at=now - timedelta(minutes=11),
                locked_by="stopped-worker",
            )
        )
        await setup.commit()

    async with postgres_events.sessions() as session:
        result = await OutboxDispatcher(bus, worker_id="replacement-worker").run_once(session)
        delivery = await session.scalar(select(EventDelivery))

    assert result["processed"] == 1
    assert calls == [event_id]
    assert delivery is not None
    assert delivery.status == "SUCCEEDED"
    assert delivery.attempt_count == 2
    assert delivery.locked_at is None
    assert delivery.locked_by is None


def test_module_context_receives_bound_real_event_adapter() -> None:
    bus = InProcessEventBus()
    manifest = parse_manifest(
        {
            "manifest_version": 1,
            "id": "example-module",
            "name": "Example module",
            "version": "1.0.0",
            "requires": {"host": ">=0.1.0,<1.0.0", "sdk": ">=1.0.0,<2.0.0"},
        }
    )
    context = ModuleContextFactory(event_bus=bus).create(
        manifest,
        ModuleRegistrationContext(),
    )

    assert isinstance(context.events, HostEventBusAdapter)
    context.events.subscribe(
        "other.created",
        handler_id="example-module.other-created",
        versions=frozenset({1}),
        handler=lambda _event: None,
    )
    assert bus.subscriptions[0].handler_id == "example-module.other-created"


def test_reference_module_registers_subscriber_only_through_public_sdk() -> None:
    bus = InProcessEventBus()
    runtime = create_module_runtime(
        enabled_module_ids=("test-event-subscriber",),
        discovery_providers=(FakeDiscovery((SUBSCRIBER_DEFINITION,)),),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(event_bus=bus),
    )

    runtime.register(FastAPI())

    assert [item.handler_id for item in bus.subscriptions] == [
        "test-event-subscriber.example-created"
    ]
    fixture_path = Path(__file__).resolve().parent / "fixtures/event_subscriber_module.py"
    tree = ast.parse(fixture_path.read_text(encoding="utf-8"))
    app_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("app.")
    }
    assert app_imports == {"app.platform.modules.sdk"}


@pytest.mark.asyncio
async def test_polygon_pilot_queues_public_contract_without_importing_consumer() -> None:
    class RecordingSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

    session = RecordingSession()
    polygon_id = uuid.uuid4()
    await enqueue_polygon_event(session, PolygonCreated(polygon_id))  # type: ignore[arg-type]

    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, DomainEventOutbox)
    assert row.event_name == "polygons.created"
    assert row.payload == {"polygon_id": str(polygon_id)}

    bus = InProcessEventBus()
    register_polygon_event_handlers(bus)
    assert [item.handler_id for item in bus.subscriptions] == [
        "polygons.enrich-created-address",
        "polygons.enrich-updated-address",
        "notifications.polygon-updated",
        "notifications.polygon-deleted",
        "social.cancel-deleted-polygon",
    ]

    producer_path = Path(__file__).resolve().parents[1] / "app/services/polygon_events.py"
    tree = ast.parse(producer_path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    app_imports = {module for module in imports if module.startswith("app.")}
    assert app_imports == {"app.platform.modules.sdk"}
    assert "app.services.polygon_event_handlers" not in imports
    assert "app.services.notifications" not in imports
    assert "app.services.social_publishing" not in imports

"""Fachneutrale Domain-Event- und Transactional-Outbox-Infrastruktur."""

from app.platform.events.bus import (
    DuplicateEventHandlerError,
    EventDispatchError,
    EventSubscription,
    InProcessEventBus,
    UnsupportedEventVersionError,
)
from app.platform.events.outbox import (
    HostEventBusAdapter,
    OutboxDispatcher,
    RetryPolicy,
)

__all__ = [
    "DuplicateEventHandlerError",
    "EventDispatchError",
    "EventSubscription",
    "HostEventBusAdapter",
    "InProcessEventBus",
    "OutboxDispatcher",
    "RetryPolicy",
    "UnsupportedEventVersionError",
]

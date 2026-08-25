"""Deterministische In-Process-Registry und direkte Event-Zustellung."""

import inspect
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.platform.modules.sdk import EventEnvelope, EventHandler

_EVENT_NAME = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
_HANDLER_ID = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")


class DuplicateEventHandlerError(ValueError):
    """Eine persistente Handler-ID wurde mehr als einmal registriert."""


class UnsupportedEventVersionError(RuntimeError):
    """Subscriber existieren, aber keiner unterstützt die Event-Version."""


class EventDispatchError(RuntimeError):
    """Direkte Zustellung ist fehlgeschlagen und wird an den Publisher propagiert."""

    def __init__(self, envelope: EventEnvelope, handler_id: str) -> None:
        super().__init__(
            f'Handler "{handler_id}" failed for event '
            f'"{envelope.event_name}" version {envelope.event_version} '
            f"({envelope.event_id})."
        )
        self.event_id = envelope.event_id
        self.event_name = envelope.event_name
        self.event_version = envelope.event_version
        self.handler_id = handler_id


@dataclass(frozen=True, slots=True)
class EventSubscription:
    event_name: str
    handler_id: str
    versions: frozenset[int]
    handler: EventHandler
    registration_index: int


class InProcessEventBus:
    """Deploy-time Subscriber-Registry mit deterministischer serieller Zustellung."""

    def __init__(self) -> None:
        self._subscriptions: list[EventSubscription] = []
        self._handler_ids: set[str] = set()
        self._sealed = False

    @property
    def subscriptions(self) -> tuple[EventSubscription, ...]:
        return tuple(self._subscriptions)

    def subscribe(
        self,
        event_name: str,
        *,
        handler_id: str,
        versions: frozenset[int],
        handler: EventHandler,
    ) -> None:
        if self._sealed:
            raise RuntimeError("Event subscriber registration is closed.")
        if not _EVENT_NAME.fullmatch(event_name):
            raise ValueError("Event names must use the form <module-id>.<event-name>.")
        if len(event_name) > 160:
            raise ValueError("Event names must not exceed 160 characters.")
        if not _HANDLER_ID.fullmatch(handler_id):
            raise ValueError("Handler IDs must be stable namespaced identifiers.")
        if len(handler_id) > 160:
            raise ValueError("Handler IDs must not exceed 160 characters.")
        if not versions or any(version < 1 for version in versions):
            raise ValueError("Subscribers must declare positive supported event versions.")
        if handler_id in self._handler_ids:
            raise DuplicateEventHandlerError(f'Event handler ID "{handler_id}" is duplicated.')
        self._handler_ids.add(handler_id)
        self._subscriptions.append(
            EventSubscription(
                event_name=event_name,
                handler_id=handler_id,
                versions=frozenset(versions),
                handler=handler,
                registration_index=len(self._subscriptions),
            )
        )

    def seal(self) -> None:
        self._sealed = True

    def subscriptions_for(
        self,
        event_name: str,
        event_version: int,
        *,
        fail_on_unsupported: bool = True,
    ) -> Sequence[EventSubscription]:
        named = tuple(
            subscription
            for subscription in self._subscriptions
            if subscription.event_name == event_name
        )
        supported = tuple(
            subscription for subscription in named if event_version in subscription.versions
        )
        if named and not supported and fail_on_unsupported:
            raise UnsupportedEventVersionError(
                f'No handler for event "{event_name}" supports version {event_version}.'
            )
        return supported

    def subscription(self, handler_id: str) -> EventSubscription | None:
        return next(
            (
                subscription
                for subscription in self._subscriptions
                if subscription.handler_id == handler_id
            ),
            None,
        )

    async def dispatch(self, envelope: EventEnvelope) -> None:
        for subscription in self.subscriptions_for(
            envelope.event_name,
            envelope.event_version,
        ):
            await self.dispatch_to(subscription, envelope)

    async def dispatch_to(
        self,
        subscription: EventSubscription,
        envelope: EventEnvelope,
    ) -> None:
        try:
            result = subscription.handler(envelope)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            raise EventDispatchError(envelope, subscription.handler_id) from exc

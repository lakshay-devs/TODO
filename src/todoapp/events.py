"""A tiny synchronous event bus (observer pattern)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Callable


class EventType(Enum):
    TASK_CREATED = auto()
    TASK_UPDATED = auto()
    TASK_DELETED = auto()
    STATUS_CHANGED = auto()
    TASK_COMPLETED = auto()


@dataclass(frozen=True, slots=True)
class Event:
    type: EventType
    task_id: str
    payload: dict = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Listener = Callable[[Event], None]


class EventBus:
    """Register listeners per event type (or globally) and dispatch."""

    def __init__(self) -> None:
        self._listeners: dict[EventType, list[Listener]] = defaultdict(list)
        self._global: list[Listener] = []
        self._log: list[Event] = []

    def subscribe(self, event_type: EventType, listener: Listener) -> Callable[[], None]:
        self._listeners[event_type].append(listener)
        return lambda: self._listeners[event_type].remove(listener)

    def subscribe_all(self, listener: Listener) -> Callable[[], None]:
        self._global.append(listener)
        return lambda: self._global.remove(listener)

    def publish(self, event: Event) -> None:
        self._log.append(event)
        for listener in (*self._listeners.get(event.type, ()), *self._global):
            listener(event)

    @property
    def history(self) -> tuple[Event, ...]:
        return tuple(self._log)

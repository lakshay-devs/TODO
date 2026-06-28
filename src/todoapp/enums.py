"""Enumerations used across the todo domain."""

from __future__ import annotations

from enum import Enum, IntEnum, auto


class Priority(IntEnum):
    """Task priority. Higher value == more urgent (sortable as int)."""

    TRIVIAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def from_str(cls, value: str) -> "Priority":
        try:
            return cls[value.strip().upper()]
        except KeyError as exc:
            raise ValueError(f"unknown priority: {value!r}") from exc

    @property
    def label(self) -> str:
        return self.name.capitalize()


class Status(Enum):
    """Lifecycle state of a task."""

    TODO = auto()
    IN_PROGRESS = auto()
    BLOCKED = auto()
    DONE = auto()
    ARCHIVED = auto()

    @property
    def is_terminal(self) -> bool:
        return self in (Status.DONE, Status.ARCHIVED)

    @property
    def is_active(self) -> bool:
        return self in (Status.TODO, Status.IN_PROGRESS, Status.BLOCKED)


class RecurrenceUnit(Enum):
    """Unit used by a recurrence rule."""

    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    YEARLY = auto()


# Allowed status transitions. Guard rail for the state machine.
ALLOWED_TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.TODO: frozenset({Status.IN_PROGRESS, Status.BLOCKED, Status.DONE, Status.ARCHIVED}),
    Status.IN_PROGRESS: frozenset({Status.TODO, Status.BLOCKED, Status.DONE, Status.ARCHIVED}),
    Status.BLOCKED: frozenset({Status.TODO, Status.IN_PROGRESS, Status.ARCHIVED}),
    Status.DONE: frozenset({Status.TODO, Status.ARCHIVED}),
    Status.ARCHIVED: frozenset({Status.TODO}),
}


def can_transition(src: Status, dst: Status) -> bool:
    """Return True if moving from ``src`` to ``dst`` is permitted."""

    if src is dst:
        return True
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())

"""Core domain models: Tag, RecurrenceRule, Task."""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone

from .enums import Priority, RecurrenceUnit, Status, can_transition
from .exceptions import InvalidTransitionError, ValidationError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass(frozen=True, slots=True, order=True)
class Tag:
    """Immutable, comparable label. Normalised to lowercase."""

    name: str

    def __post_init__(self) -> None:
        cleaned = self.name.strip().lower().lstrip("#")
        if not cleaned:
            raise ValidationError("tag name cannot be empty")
        if any(c.isspace() for c in cleaned):
            raise ValidationError("tag name cannot contain whitespace")
        object.__setattr__(self, "name", cleaned)

    def __str__(self) -> str:
        return f"#{self.name}"


@dataclass(frozen=True, slots=True)
class RecurrenceRule:
    """Defines how a completed task spawns its next occurrence."""

    unit: RecurrenceUnit
    interval: int = 1

    def __post_init__(self) -> None:
        if self.interval < 1:
            raise ValidationError("recurrence interval must be >= 1")

    def next_after(self, anchor: date) -> date:
        n = self.interval
        match self.unit:
            case RecurrenceUnit.DAILY:
                return anchor + timedelta(days=n)
            case RecurrenceUnit.WEEKLY:
                return anchor + timedelta(weeks=n)
            case RecurrenceUnit.MONTHLY:
                month = anchor.month - 1 + n
                year = anchor.year + month // 12
                month = month % 12 + 1
                day = min(anchor.day, _days_in_month(year, month))
                return date(year, month, day)
            case RecurrenceUnit.YEARLY:
                try:
                    return anchor.replace(year=anchor.year + n)
                except ValueError:  # Feb 29 -> non-leap year
                    return anchor.replace(year=anchor.year + n, day=28)
        raise ValidationError(f"unhandled recurrence unit: {self.unit}")


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days


@dataclass(slots=True)
class Task:
    """A single todo item. Mutable aggregate root."""

    title: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    status: Status = Status.TODO
    due: date | None = None
    tags: set[Tag] = field(default_factory=set)
    dependencies: set[str] = field(default_factory=set)
    recurrence: RecurrenceRule | None = None
    id: str = field(default_factory=_new_id)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    _seq: int = field(default_factory=itertools.count().__next__, repr=False)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        if not self.title:
            raise ValidationError("task title cannot be empty")

    # --- mutation helpers (all stamp updated_at) --------------------------
    def touch(self) -> None:
        self.updated_at = _utcnow()

    def rename(self, title: str) -> None:
        title = title.strip()
        if not title:
            raise ValidationError("task title cannot be empty")
        self.title = title
        self.touch()

    def set_priority(self, priority: Priority) -> None:
        self.priority = priority
        self.touch()

    def add_tag(self, tag: Tag | str) -> None:
        self.tags.add(tag if isinstance(tag, Tag) else Tag(tag))
        self.touch()

    def remove_tag(self, tag: Tag | str) -> None:
        self.tags.discard(tag if isinstance(tag, Tag) else Tag(tag))
        self.touch()

    def add_dependency(self, task_id: str) -> None:
        if task_id == self.id:
            raise ValidationError("task cannot depend on itself")
        self.dependencies.add(task_id)
        self.touch()

    def remove_dependency(self, task_id: str) -> None:
        self.dependencies.discard(task_id)
        self.touch()

    def transition_to(self, dst: Status) -> None:
        if not can_transition(self.status, dst):
            raise InvalidTransitionError(self.status, dst)
        self.status = dst
        self.completed_at = _utcnow() if dst is Status.DONE else None
        self.touch()

    # --- derived properties ----------------------------------------------
    @property
    def is_done(self) -> bool:
        return self.status is Status.DONE

    @property
    def is_overdue(self) -> bool:
        return (
            self.due is not None
            and not self.status.is_terminal
            and self.due < date.today()
        )

    @property
    def days_until_due(self) -> int | None:
        if self.due is None:
            return None
        return (self.due - date.today()).days

    @property
    def age_days(self) -> int:
        return (_utcnow() - self.created_at).days

    def spawn_next(self) -> "Task | None":
        """Create the next occurrence of a recurring task, if any."""
        if self.recurrence is None or self.due is None:
            return None
        return replace(
            self,
            id=_new_id(),
            status=Status.TODO,
            completed_at=None,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            due=self.recurrence.next_after(self.due),
            tags=set(self.tags),
            dependencies=set(),
            _seq=next(_GLOBAL_SEQ),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.label,
            "status": self.status.name,
            "due": self.due.isoformat() if self.due else None,
            "tags": sorted(t.name for t in self.tags),
            "dependencies": sorted(self.dependencies),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __str__(self) -> str:
        mark = {
            Status.TODO: " ",
            Status.IN_PROGRESS: "~",
            Status.BLOCKED: "!",
            Status.DONE: "x",
            Status.ARCHIVED: "-",
        }[self.status]
        due = f" (due {self.due})" if self.due else ""
        tags = (" " + " ".join(str(t) for t in sorted(self.tags))) if self.tags else ""
        return f"[{mark}] {self.priority.label[:4]:<4} {self.title}{due}{tags}  <{self.id}>"


_GLOBAL_SEQ = itertools.count(1_000_000)

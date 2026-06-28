"""Composable filters via the Specification pattern.

Specifications are predicates that can be combined with ``&``, ``|`` and ``~``::

    spec = ByStatus(Status.TODO) & (IsOverdue() | HasTag("urgent"))
    [t for t in tasks if spec(t)]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Callable

from .enums import Priority, Status
from .models import Tag, Task


class Specification(ABC):
    """Base predicate over a Task."""

    @abstractmethod
    def is_satisfied_by(self, task: Task) -> bool: ...

    def __call__(self, task: Task) -> bool:
        return self.is_satisfied_by(task)

    def __and__(self, other: "Specification") -> "Specification":
        return AndSpec(self, other)

    def __or__(self, other: "Specification") -> "Specification":
        return OrSpec(self, other)

    def __invert__(self) -> "Specification":
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, *specs: Specification) -> None:
        self.specs = specs

    def is_satisfied_by(self, task: Task) -> bool:
        return all(s.is_satisfied_by(task) for s in self.specs)


class OrSpec(Specification):
    def __init__(self, *specs: Specification) -> None:
        self.specs = specs

    def is_satisfied_by(self, task: Task) -> bool:
        return any(s.is_satisfied_by(task) for s in self.specs)


class NotSpec(Specification):
    def __init__(self, spec: Specification) -> None:
        self.spec = spec

    def is_satisfied_by(self, task: Task) -> bool:
        return not self.spec.is_satisfied_by(task)


class Always(Specification):
    def is_satisfied_by(self, task: Task) -> bool:
        return True


class Predicate(Specification):
    """Wrap an arbitrary callable as a specification."""

    def __init__(self, fn: Callable[[Task], bool]) -> None:
        self.fn = fn

    def is_satisfied_by(self, task: Task) -> bool:
        return self.fn(task)


# --- concrete leaf specifications ----------------------------------------
class ByStatus(Specification):
    def __init__(self, *statuses: Status) -> None:
        self.statuses = frozenset(statuses)

    def is_satisfied_by(self, task: Task) -> bool:
        return task.status in self.statuses


class ByPriority(Specification):
    def __init__(self, minimum: Priority) -> None:
        self.minimum = minimum

    def is_satisfied_by(self, task: Task) -> bool:
        return task.priority >= self.minimum


class HasTag(Specification):
    def __init__(self, tag: Tag | str) -> None:
        self.tag = tag if isinstance(tag, Tag) else Tag(tag)

    def is_satisfied_by(self, task: Task) -> bool:
        return self.tag in task.tags


class HasAllTags(Specification):
    def __init__(self, *tags: Tag | str) -> None:
        self.tags = {t if isinstance(t, Tag) else Tag(t) for t in tags}

    def is_satisfied_by(self, task: Task) -> bool:
        return self.tags <= task.tags


class IsOverdue(Specification):
    def is_satisfied_by(self, task: Task) -> bool:
        return task.is_overdue


class DueBefore(Specification):
    def __init__(self, when: date) -> None:
        self.when = when

    def is_satisfied_by(self, task: Task) -> bool:
        return task.due is not None and task.due <= self.when


class TextMatches(Specification):
    def __init__(self, needle: str) -> None:
        self.needle = needle.lower()

    def is_satisfied_by(self, task: Task) -> bool:
        n = self.needle
        return n in task.title.lower() or n in task.description.lower()


class IsActive(Specification):
    def is_satisfied_by(self, task: Task) -> bool:
        return task.status.is_active

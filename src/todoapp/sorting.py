"""Reusable sort keys / strategies for task lists."""

from __future__ import annotations

from datetime import date
from typing import Callable

from .models import Task

SortKey = Callable[[Task], object]


def by_priority_desc(task: Task) -> tuple:
    # highest priority first, then soonest due, then oldest
    far = date.max
    return (-int(task.priority), task.due or far, task._seq)


def by_due_date(task: Task) -> tuple:
    far = date.max
    return (task.due or far, -int(task.priority))


def by_created(task: Task) -> int:
    return task._seq


def by_title(task: Task) -> str:
    return task.title.lower()


def by_status(task: Task) -> tuple:
    return (task.status.value, -int(task.priority))


STRATEGIES: dict[str, SortKey] = {
    "priority": by_priority_desc,
    "due": by_due_date,
    "created": by_created,
    "title": by_title,
    "status": by_status,
}


def sort_tasks(tasks: list[Task], strategy: str = "priority", reverse: bool = False) -> list[Task]:
    try:
        key = STRATEGIES[strategy]
    except KeyError as exc:
        raise ValueError(f"unknown sort strategy: {strategy!r}") from exc
    return sorted(tasks, key=key, reverse=reverse)

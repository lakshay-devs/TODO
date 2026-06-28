"""Storage abstraction plus an in-memory implementation."""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Iterable, Iterator

from .exceptions import DuplicateTaskError, TaskNotFoundError
from .models import Task


class TaskRepository(ABC):
    """Persistence port. Swap the impl without touching the service."""

    @abstractmethod
    def add(self, task: Task) -> Task: ...

    @abstractmethod
    def get(self, task_id: str) -> Task: ...

    @abstractmethod
    def update(self, task: Task) -> Task: ...

    @abstractmethod
    def delete(self, task_id: str) -> Task: ...

    @abstractmethod
    def list(self) -> list[Task]: ...

    @abstractmethod
    def exists(self, task_id: str) -> bool: ...

    def __len__(self) -> int:
        return len(self.list())

    def __iter__(self) -> Iterator[Task]:
        return iter(self.list())

    def __contains__(self, task_id: object) -> bool:
        return isinstance(task_id, str) and self.exists(task_id)


class InMemoryTaskRepository(TaskRepository):
    """Dict-backed store. Insertion order preserved (dict ordering)."""

    def __init__(self, tasks: Iterable[Task] | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        for task in tasks or ():
            self.add(task)

    def add(self, task: Task) -> Task:
        if task.id in self._tasks:
            raise DuplicateTaskError(task.id)
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFoundError(task_id) from exc

    def update(self, task: Task) -> Task:
        if task.id not in self._tasks:
            raise TaskNotFoundError(task.id)
        self._tasks[task.id] = task
        return task

    def delete(self, task_id: str) -> Task:
        try:
            return self._tasks.pop(task_id)
        except KeyError as exc:
            raise TaskNotFoundError(task_id) from exc

    def list(self) -> list[Task]:
        return list(self._tasks.values())

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks

    def snapshot(self) -> dict[str, Task]:
        """Deep copy of the whole store (used for undo/redo restore)."""
        return copy.deepcopy(self._tasks)

    def restore(self, snapshot: dict[str, Task]) -> None:
        self._tasks = copy.deepcopy(snapshot)

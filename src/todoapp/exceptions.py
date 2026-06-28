"""Domain-specific exception hierarchy."""

from __future__ import annotations


class TodoError(Exception):
    """Base class for all todo application errors."""


class TaskNotFoundError(TodoError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"task not found: {task_id}")
        self.task_id = task_id


class DuplicateTaskError(TodoError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"duplicate task id: {task_id}")
        self.task_id = task_id


class InvalidTransitionError(TodoError):
    def __init__(self, src: object, dst: object) -> None:
        super().__init__(f"illegal status transition: {src} -> {dst}")
        self.src = src
        self.dst = dst


class ValidationError(TodoError):
    """Raised when a model fails its invariants."""


class CyclicDependencyError(TodoError):
    """Raised when adding a dependency would create a cycle."""

    def __init__(self, task_id: str, dep_id: str) -> None:
        super().__init__(f"dependency {dep_id} -> {task_id} would create a cycle")
        self.task_id = task_id
        self.dep_id = dep_id


class NothingToUndoError(TodoError):
    pass


class NothingToRedoError(TodoError):
    pass

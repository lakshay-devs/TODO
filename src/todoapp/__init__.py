"""todoapp — an in-memory todo engine.

Public API re-exported for convenience::

    from todoapp import TodoService, Priority, Status, Tag

Run the bundled demo with ``uv run todoapp`` or ``python -m todoapp``.
"""

from __future__ import annotations

from .analytics import Analyzer, Stats
from .commands import (
    AddTaskCommand,
    Command,
    CommandInvoker,
    DeleteTaskCommand,
    MacroCommand,
    TransitionCommand,
    UpdateFieldCommand,
)
from .enums import Priority, RecurrenceUnit, Status, can_transition
from .events import Event, EventBus, EventType
from .exceptions import (
    CyclicDependencyError,
    DuplicateTaskError,
    InvalidTransitionError,
    TaskNotFoundError,
    TodoError,
    ValidationError,
)
from .models import RecurrenceRule, Tag, Task
from .persistence import (
    FileTaskRepository,
    record_to_task,
    task_to_record,
)
from .repository import InMemoryTaskRepository, TaskRepository
from .service import TodoService
from .sorting import sort_tasks
from .specifications import (
    Always,
    ByPriority,
    ByStatus,
    DueBefore,
    HasAllTags,
    HasTag,
    IsActive,
    IsOverdue,
    Predicate,
    Specification,
    TextMatches,
)

__version__ = "0.1.0"

__all__ = [
    "Analyzer",
    "Stats",
    "AddTaskCommand",
    "Command",
    "CommandInvoker",
    "DeleteTaskCommand",
    "MacroCommand",
    "TransitionCommand",
    "UpdateFieldCommand",
    "Priority",
    "RecurrenceUnit",
    "Status",
    "can_transition",
    "Event",
    "EventBus",
    "EventType",
    "CyclicDependencyError",
    "DuplicateTaskError",
    "InvalidTransitionError",
    "TaskNotFoundError",
    "TodoError",
    "ValidationError",
    "RecurrenceRule",
    "Tag",
    "Task",
    "InMemoryTaskRepository",
    "TaskRepository",
    "FileTaskRepository",
    "record_to_task",
    "task_to_record",
    "TodoService",
    "sort_tasks",
    "Always",
    "ByPriority",
    "ByStatus",
    "DueBefore",
    "HasAllTags",
    "HasTag",
    "IsActive",
    "IsOverdue",
    "Predicate",
    "Specification",
    "TextMatches",
]


def main() -> None:
    """Console-script entrypoint (see ``[project.scripts]``)."""
    from .cli import main as _main

    _main()

"""Command pattern with an undo/redo stack.

Every mutating operation is modelled as a Command that knows how to
``execute`` and ``undo`` itself against the repository.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod

from .enums import Status
from .exceptions import NothingToRedoError, NothingToUndoError
from .models import Task
from .repository import TaskRepository


class Command(ABC):
    """A reversible unit of work."""

    name: str = "command"

    @abstractmethod
    def execute(self) -> object: ...

    @abstractmethod
    def undo(self) -> None: ...

    def __str__(self) -> str:
        return self.name


class AddTaskCommand(Command):
    name = "add"

    def __init__(self, repo: TaskRepository, task: Task) -> None:
        self.repo = repo
        self.task = task

    def execute(self) -> Task:
        return self.repo.add(self.task)

    def undo(self) -> None:
        self.repo.delete(self.task.id)


class DeleteTaskCommand(Command):
    name = "delete"

    def __init__(self, repo: TaskRepository, task_id: str) -> None:
        self.repo = repo
        self.task_id = task_id
        self._backup: Task | None = None

    def execute(self) -> Task:
        self._backup = copy.deepcopy(self.repo.get(self.task_id))
        return self.repo.delete(self.task_id)

    def undo(self) -> None:
        if self._backup is not None:
            self.repo.add(self._backup)


class UpdateFieldCommand(Command):
    """Generic single-field setter that records the previous value."""

    name = "update"

    def __init__(self, repo: TaskRepository, task_id: str, field: str, value: object) -> None:
        self.repo = repo
        self.task_id = task_id
        self.field = field
        self.value = value
        self._old: object = None

    def execute(self) -> Task:
        task = self.repo.get(self.task_id)
        self._old = getattr(task, self.field)
        setattr(task, self.field, self.value)
        task.touch()
        return self.repo.update(task)

    def undo(self) -> None:
        task = self.repo.get(self.task_id)
        setattr(task, self.field, self._old)
        task.touch()
        self.repo.update(task)


class TransitionCommand(Command):
    name = "transition"

    def __init__(self, repo: TaskRepository, task_id: str, dst: Status) -> None:
        self.repo = repo
        self.task_id = task_id
        self.dst = dst
        self._old: Status | None = None

    def execute(self) -> Task:
        task = self.repo.get(self.task_id)
        self._old = task.status
        task.transition_to(self.dst)
        return self.repo.update(task)

    def undo(self) -> None:
        if self._old is None:
            return
        task = self.repo.get(self.task_id)
        task.status = self._old
        task.completed_at = None if self._old is not Status.DONE else task.completed_at
        task.touch()
        self.repo.update(task)


class MacroCommand(Command):
    """Run several commands atomically; undo reverses them in order."""

    name = "macro"

    def __init__(self, *commands: Command) -> None:
        self.commands = list(commands)

    def execute(self) -> list[object]:
        done: list[Command] = []
        results: list[object] = []
        try:
            for cmd in self.commands:
                results.append(cmd.execute())
                done.append(cmd)
        except Exception:
            for cmd in reversed(done):  # roll back partial application
                cmd.undo()
            raise
        return results

    def undo(self) -> None:
        for cmd in reversed(self.commands):
            cmd.undo()


class CommandInvoker:
    """Executes commands and maintains undo / redo history."""

    def __init__(self, history_limit: int = 100) -> None:
        self._undo: list[Command] = []
        self._redo: list[Command] = []
        self._limit = history_limit

    def run(self, command: Command) -> object:
        result = command.execute()
        self._undo.append(command)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()
        return result

    def undo(self) -> Command:
        if not self._undo:
            raise NothingToUndoError("undo stack empty")
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)
        return cmd

    def redo(self) -> Command:
        if not self._redo:
            raise NothingToRedoError("redo stack empty")
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)
        return cmd

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def history(self) -> list[str]:
        return [c.name for c in self._undo]

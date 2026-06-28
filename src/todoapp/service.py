"""High-level facade wiring repository, commands, events and queries."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from .analytics import Analyzer, Stats
from .commands import (
    AddTaskCommand,
    CommandInvoker,
    DeleteTaskCommand,
    MacroCommand,
    TransitionCommand,
    UpdateFieldCommand,
)
from .enums import Priority, Status
from .events import Event, EventBus, EventType
from .exceptions import CyclicDependencyError, TaskNotFoundError, ValidationError
from .models import RecurrenceRule, Tag, Task
from .repository import InMemoryTaskRepository, TaskRepository
from .sorting import sort_tasks
from .specifications import Specification


class TodoService:
    """Primary application entrypoint.

    Coordinates the repository, the undo/redo invoker, the event bus and the
    analytics engine behind one convenient API.
    """

    def __init__(
        self,
        repo: TaskRepository | None = None,
        bus: EventBus | None = None,
        analyzer: Analyzer | None = None,
    ) -> None:
        # NB: an empty repo is falsy (TaskRepository defines __len__), so test
        # against None explicitly instead of using `repo or ...`.
        self.repo = repo if repo is not None else InMemoryTaskRepository()
        self.bus = bus if bus is not None else EventBus()
        self.analyzer = analyzer if analyzer is not None else Analyzer()
        self.invoker = CommandInvoker()

    # --- creation ---------------------------------------------------------
    def add(
        self,
        title: str,
        *,
        description: str = "",
        priority: Priority | str = Priority.MEDIUM,
        due: date | None = None,
        tags: Iterable[str | Tag] = (),
        recurrence: RecurrenceRule | None = None,
    ) -> Task:
        if isinstance(priority, str):
            priority = Priority.from_str(priority)
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due=due,
            tags={t if isinstance(t, Tag) else Tag(t) for t in tags},
            recurrence=recurrence,
        )
        self.invoker.run(AddTaskCommand(self.repo, task))
        self._emit(EventType.TASK_CREATED, task.id, {"title": task.title})
        return task

    # --- retrieval --------------------------------------------------------
    def get(self, task_id: str) -> Task:
        return self.repo.get(task_id)

    def all(self) -> list[Task]:
        return self.repo.list()

    def pending(self) -> list[Task]:
        """Active (non-terminal) tasks, highest priority first."""
        active = [t for t in self.repo.list() if t.status.is_active]
        return sort_tasks(active, strategy="priority")

    def find(
        self,
        spec: Specification | None = None,
        *,
        sort: str = "priority",
        reverse: bool = False,
    ) -> list[Task]:
        tasks = self.repo.list()
        if spec is not None:
            tasks = [t for t in tasks if spec(t)]
        return sort_tasks(tasks, strategy=sort, reverse=reverse)

    # --- mutation ---------------------------------------------------------
    def update_field(self, task_id: str, field: str, value: object) -> Task:
        allowed = {"title", "description", "priority", "due", "recurrence"}
        if field not in allowed:
            raise ValidationError(f"field {field!r} is not editable via update_field")
        task = self.invoker.run(UpdateFieldCommand(self.repo, task_id, field, value))
        self._emit(EventType.TASK_UPDATED, task_id, {"field": field})
        return task  # type: ignore[return-value]

    def set_status(self, task_id: str, status: Status) -> Task:
        if status is Status.DONE:
            self._assert_dependencies_done(task_id)
        task = self.invoker.run(TransitionCommand(self.repo, task_id, status))
        self._emit(EventType.STATUS_CHANGED, task_id, {"status": status.name})
        if status is Status.DONE:
            self._emit(EventType.TASK_COMPLETED, task_id, {})
            self._maybe_spawn_recurrence(task_id)  # type: ignore[arg-type]
        return task  # type: ignore[return-value]

    def complete(self, task_id: str) -> Task:
        return self.set_status(task_id, Status.DONE)

    def delete(self, task_id: str) -> Task:
        task = self.invoker.run(DeleteTaskCommand(self.repo, task_id))
        self._emit(EventType.TASK_DELETED, task_id, {})
        return task  # type: ignore[return-value]

    def bulk_complete(self, *task_ids: str) -> list[Task]:
        macro = MacroCommand(
            *(TransitionCommand(self.repo, tid, Status.DONE) for tid in task_ids)
        )
        return self.invoker.run(macro)  # type: ignore[return-value]

    # --- tags -------------------------------------------------------------
    def tag(self, task_id: str, *tags: str) -> Task:
        task = self.repo.get(task_id)
        for t in tags:
            task.add_tag(t)
        self.repo.update(task)
        self._emit(EventType.TASK_UPDATED, task_id, {"tags": list(tags)})
        return task

    # --- dependencies + DAG ----------------------------------------------
    def add_dependency(self, task_id: str, depends_on: str) -> Task:
        if not self.repo.exists(depends_on):
            raise TaskNotFoundError(depends_on)
        if self._creates_cycle(task_id, depends_on):
            raise CyclicDependencyError(task_id, depends_on)
        task = self.repo.get(task_id)
        task.add_dependency(depends_on)
        self.repo.update(task)
        return task

    def _creates_cycle(self, task_id: str, new_dep: str) -> bool:
        # Would task_id become reachable from new_dep? Walk new_dep's deps.
        seen: set[str] = set()
        stack = [new_dep]
        while stack:
            cur = stack.pop()
            if cur == task_id:
                return True
            if cur in seen or not self.repo.exists(cur):
                continue
            seen.add(cur)
            stack.extend(self.repo.get(cur).dependencies)
        return False

    def _assert_dependencies_done(self, task_id: str) -> None:
        task = self.repo.get(task_id)
        pending = [
            d for d in task.dependencies
            if self.repo.exists(d) and not self.repo.get(d).is_done
        ]
        if pending:
            raise ValidationError(
                f"cannot complete {task_id}: blocked by {', '.join(pending)}"
            )

    def topological_order(self) -> list[Task]:
        """Return tasks so every dependency precedes its dependents (Kahn)."""
        tasks = {t.id: t for t in self.repo.list()}
        indeg = {tid: 0 for tid in tasks}
        adj: dict[str, list[str]] = {tid: [] for tid in tasks}
        for tid, task in tasks.items():
            for dep in task.dependencies:
                if dep in tasks:
                    adj[dep].append(tid)
                    indeg[tid] += 1
        queue = sorted(t for t, d in indeg.items() if d == 0)
        order: list[str] = []
        while queue:
            cur = queue.pop(0)
            order.append(cur)
            for nxt in adj[cur]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
            queue.sort()
        if len(order) != len(tasks):
            raise CyclicDependencyError("?", "?")
        return [tasks[tid] for tid in order]

    # --- history ----------------------------------------------------------
    def undo(self) -> str:
        return self.invoker.undo().name

    def redo(self) -> str:
        return self.invoker.redo().name

    # --- analytics --------------------------------------------------------
    def stats(self) -> Stats:
        return self.analyzer.compute(self.repo.list())

    # --- internals --------------------------------------------------------
    def _emit(self, etype: EventType, task_id: str, payload: dict) -> None:
        self.bus.publish(Event(etype, task_id, payload))

    def _maybe_spawn_recurrence(self, task_id: str) -> None:
        task = self.repo.get(task_id)
        nxt = task.spawn_next()
        if nxt is not None:
            self.repo.add(nxt)
            self._emit(EventType.TASK_CREATED, nxt.id, {"recurred_from": task_id})

    def __len__(self) -> int:
        return len(self.repo)

"""JSON-file persistence adapter.

`FileTaskRepository` implements the same `TaskRepository` port as the
in-memory store, so it drops into `TodoService` unchanged::

    svc = TodoService(repo=FileTaskRepository("tasks.json"))

Tasks are kept in memory for fast access and written through to disk on
every mutation (autosave), giving full round-trip persistence.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .enums import Priority, RecurrenceUnit, Status
from .exceptions import DuplicateTaskError, TaskNotFoundError, ValidationError
from .models import RecurrenceRule, Tag, Task
from .repository import TaskRepository

SCHEMA_VERSION = 1


# --- (de)serialisation ----------------------------------------------------
def task_to_record(task: Task) -> dict[str, Any]:
    """Lossless dict for one task (round-trips via `record_to_task`)."""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "priority": int(task.priority),
        "status": task.status.name,
        "due": task.due.isoformat() if task.due else None,
        "tags": sorted(t.name for t in task.tags),
        "dependencies": sorted(task.dependencies),
        "recurrence": (
            {"unit": task.recurrence.unit.name, "interval": task.recurrence.interval}
            if task.recurrence
            else None
        ),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "_seq": task._seq,
    }


def record_to_task(rec: dict[str, Any]) -> Task:
    """Rebuild a Task from a record produced by `task_to_record`."""
    try:
        recurrence = None
        if rec.get("recurrence"):
            r = rec["recurrence"]
            recurrence = RecurrenceRule(RecurrenceUnit[r["unit"]], int(r["interval"]))
        return Task(
            title=rec["title"],
            description=rec.get("description", ""),
            priority=Priority(int(rec["priority"])),
            status=Status[rec["status"]],
            due=date.fromisoformat(rec["due"]) if rec.get("due") else None,
            tags={Tag(name) for name in rec.get("tags", ())},
            dependencies=set(rec.get("dependencies", ())),
            recurrence=recurrence,
            id=rec["id"],
            created_at=datetime.fromisoformat(rec["created_at"]),
            updated_at=datetime.fromisoformat(rec["updated_at"]),
            completed_at=(
                datetime.fromisoformat(rec["completed_at"])
                if rec.get("completed_at")
                else None
            ),
            _seq=int(rec.get("_seq", 0)),
        )
    except (KeyError, ValueError) as exc:
        raise ValidationError(f"corrupt task record: {exc}") from exc


# --- repository -----------------------------------------------------------
class FileTaskRepository(TaskRepository):
    """Dict-backed store mirrored to a JSON file on every write."""

    def __init__(self, path: str | os.PathLike[str], *, autosave: bool = True) -> None:
        self.path = Path(path)
        self.autosave = autosave
        self._tasks: dict[str, Task] = {}
        if self.path.exists():
            self.load()

    # --- TaskRepository port ---------------------------------------------
    def add(self, task: Task) -> Task:
        if task.id in self._tasks:
            raise DuplicateTaskError(task.id)
        self._tasks[task.id] = task
        self._flush()
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
        self._flush()
        return task

    def delete(self, task_id: str) -> Task:
        try:
            task = self._tasks.pop(task_id)
        except KeyError as exc:
            raise TaskNotFoundError(task_id) from exc
        self._flush()
        return task

    def list(self) -> list[Task]:
        return list(self._tasks.values())

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks

    # --- disk I/O ---------------------------------------------------------
    def load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        version = raw.get("version")
        if version != SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported schema version {version!r} (expected {SCHEMA_VERSION})"
            )
        self._tasks = {
            rec["id"]: record_to_task(rec) for rec in raw.get("tasks", [])
        }

    def save(self) -> None:
        self._write_atomic(
            {
                "version": SCHEMA_VERSION,
                "tasks": [task_to_record(t) for t in self._tasks.values()],
            }
        )

    def _flush(self) -> None:
        if self.autosave:
            self.save()

    def _write_atomic(self, payload: dict[str, Any]) -> None:
        """Write via temp file + rename so a crash never truncates data."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

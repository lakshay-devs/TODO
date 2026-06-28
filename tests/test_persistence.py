"""Tests for the JSON file persistence adapter."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from todoapp import (
    FileTaskRepository,
    Priority,
    RecurrenceRule,
    RecurrenceUnit,
    Status,
    Tag,
    Task,
    TodoService,
    ValidationError,
)
from todoapp.persistence import SCHEMA_VERSION, record_to_task, task_to_record


def _sample_task() -> Task:
    return Task(
        title="ship it",
        description="cut the release",
        priority=Priority.CRITICAL,
        status=Status.IN_PROGRESS,
        due=date.today() + timedelta(days=3),
        tags={Tag("work"), Tag("ops")},
        dependencies={"abc123"},
        recurrence=RecurrenceRule(RecurrenceUnit.WEEKLY, 2),
    )


def test_record_roundtrip_preserves_all_fields():
    original = _sample_task()
    clone = record_to_task(task_to_record(original))
    assert clone.id == original.id
    assert clone.title == original.title
    assert clone.description == original.description
    assert clone.priority is original.priority
    assert clone.status is original.status
    assert clone.due == original.due
    assert clone.tags == original.tags
    assert clone.dependencies == original.dependencies
    assert clone.recurrence == original.recurrence
    assert clone.created_at == original.created_at
    assert clone.completed_at == original.completed_at


def test_file_repo_persists_across_instances(tmp_path):
    db = tmp_path / "tasks.json"
    repo = FileTaskRepository(db)
    t = _sample_task()
    repo.add(t)

    assert db.exists()
    # fresh instance reads the same data back
    reopened = FileTaskRepository(db)
    assert reopened.exists(t.id)
    assert reopened.get(t.id).title == "ship it"
    assert len(reopened) == 1


def test_file_repo_reflects_delete(tmp_path):
    db = tmp_path / "tasks.json"
    repo = FileTaskRepository(db)
    t = _sample_task()
    repo.add(t)
    repo.delete(t.id)
    assert not FileTaskRepository(db).exists(t.id)


def test_service_works_on_file_repo(tmp_path):
    db = tmp_path / "tasks.json"
    svc = TodoService(repo=FileTaskRepository(db))
    a = svc.add("a", priority="high", tags=["x"])
    b = svc.add("b")
    svc.add_dependency(b.id, a.id)
    svc.complete(a.id)
    svc.complete(b.id)

    # rehydrate through a brand new service and confirm state survived
    svc2 = TodoService(repo=FileTaskRepository(db))
    assert len(svc2) == 2
    assert svc2.get(a.id).is_done
    assert svc2.get(b.id).is_done


def test_autosave_off_does_not_write(tmp_path):
    db = tmp_path / "tasks.json"
    repo = FileTaskRepository(db, autosave=False)
    repo.add(_sample_task())
    assert not db.exists()
    repo.save()
    assert db.exists()


def test_bad_schema_version_rejected(tmp_path):
    db = tmp_path / "tasks.json"
    db.write_text(json.dumps({"version": SCHEMA_VERSION + 99, "tasks": []}))
    with pytest.raises(ValidationError):
        FileTaskRepository(db)


def test_atomic_write_leaves_no_tempfiles(tmp_path):
    db = tmp_path / "tasks.json"
    repo = FileTaskRepository(db)
    for i in range(5):
        repo.add(Task(title=f"t{i}"))
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []

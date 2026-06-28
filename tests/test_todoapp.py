"""Unit tests covering the core behaviours."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from todoapp import (
    ByPriority,
    ByStatus,
    CyclicDependencyError,
    HasTag,
    InvalidTransitionError,
    Priority,
    RecurrenceRule,
    RecurrenceUnit,
    Status,
    Tag,
    Task,
    TodoService,
    ValidationError,
)


@pytest.fixture
def svc() -> TodoService:
    return TodoService()


def test_tag_normalisation():
    assert Tag("  #Work ").name == "work"
    assert str(Tag("Home")) == "#home"
    with pytest.raises(ValidationError):
        Tag("  ")


def test_task_requires_title():
    with pytest.raises(ValidationError):
        Task(title="   ")


def test_add_and_get(svc):
    t = svc.add("a", priority="high", tags=["x"])
    assert svc.get(t.id) is t
    assert t.priority is Priority.HIGH
    assert Tag("x") in t.tags
    assert len(svc) == 1


def test_status_transition_guard(svc):
    t = svc.add("a")
    svc.set_status(t.id, Status.DONE)
    with pytest.raises(InvalidTransitionError):
        svc.get(t.id).transition_to(Status.IN_PROGRESS)


def test_completion_blocked_by_dependency(svc):
    a = svc.add("a")
    b = svc.add("b")
    svc.add_dependency(b.id, a.id)
    with pytest.raises(ValidationError):
        svc.complete(b.id)
    svc.complete(a.id)
    svc.complete(b.id)
    assert svc.get(b.id).is_done


def test_cycle_detection(svc):
    a = svc.add("a")
    b = svc.add("b")
    svc.add_dependency(b.id, a.id)
    with pytest.raises(CyclicDependencyError):
        svc.add_dependency(a.id, b.id)


def test_topological_order(svc):
    a = svc.add("a")
    b = svc.add("b")
    c = svc.add("c")
    svc.add_dependency(b.id, a.id)
    svc.add_dependency(c.id, b.id)
    order = [t.id for t in svc.topological_order()]
    assert order.index(a.id) < order.index(b.id) < order.index(c.id)


def test_undo_redo(svc):
    t = svc.add("a")
    assert len(svc) == 1
    svc.delete(t.id)
    assert len(svc) == 0
    svc.undo()  # undo delete
    assert len(svc) == 1
    svc.undo()  # undo add
    assert len(svc) == 0
    svc.redo()  # redo add
    assert len(svc) == 1


def test_specifications(svc):
    svc.add("hi", priority="critical", tags=["urgent"])
    svc.add("lo", priority="low")
    spec = ByPriority(Priority.HIGH) & ByStatus(Status.TODO)
    assert len(svc.find(spec)) == 1
    assert len(svc.find(HasTag("urgent"))) == 1


def test_overdue(svc):
    t = svc.add("late", due=date.today() - timedelta(days=1))
    assert t.is_overdue
    assert t.days_until_due == -1


def test_recurrence_spawns_next(svc):
    t = svc.add(
        "standup",
        due=date.today(),
        recurrence=RecurrenceRule(RecurrenceUnit.DAILY),
    )
    before = len(svc)
    svc.complete(t.id)
    assert len(svc) == before + 1


def test_recurrence_rule_monthly_clamps():
    rule = RecurrenceRule(RecurrenceUnit.MONTHLY)
    assert rule.next_after(date(2024, 1, 31)) == date(2024, 2, 29)


def test_stats(svc):
    svc.add("a", priority="high")
    b = svc.add("b")
    svc.complete(b.id)
    stats = svc.stats()
    assert stats.total == 2
    assert stats.completion_rate == 0.5


def test_bulk_complete(svc):
    a = svc.add("a")
    b = svc.add("b")
    svc.bulk_complete(a.id, b.id)
    assert svc.get(a.id).is_done and svc.get(b.id).is_done

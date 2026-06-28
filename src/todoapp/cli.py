"""A scripted demo that exercises the whole stack end to end."""

from __future__ import annotations

from datetime import date, timedelta

from .analytics import Analyzer
from .enums import Priority, RecurrenceUnit, Status
from .events import Event, EventType
from .models import RecurrenceRule
from .service import TodoService
from .specifications import ByPriority, ByStatus, HasTag, IsOverdue, TextMatches


def _banner(text: str) -> None:
    print(f"\n=== {text} ===")


def build_demo_service() -> TodoService:
    svc = TodoService()

    # log every event to stdout
    def logger(ev: Event) -> None:
        print(f"  · event {ev.type.name:<14} {ev.task_id}")

    svc.bus.subscribe_all(logger)
    return svc


def run_demo() -> TodoService:
    svc = build_demo_service()
    today = date.today()

    _banner("creating tasks")
    write = svc.add(
        "Write design doc",
        priority=Priority.HIGH,
        due=today + timedelta(days=2),
        tags=["work", "writing"],
    )
    review = svc.add(
        "Review design doc",
        priority=Priority.MEDIUM,
        due=today + timedelta(days=4),
        tags=["work"],
    )
    deploy = svc.add(
        "Deploy service",
        priority=Priority.CRITICAL,
        due=today + timedelta(days=5),
        tags=["work", "ops"],
    )
    svc.add(
        "Buy milk",
        priority=Priority.LOW,
        due=today - timedelta(days=1),  # overdue
        tags=["home"],
    )
    standup = svc.add(
        "Daily standup",
        priority=Priority.MEDIUM,
        due=today,
        recurrence=RecurrenceRule(RecurrenceUnit.DAILY),
        tags=["work", "meeting"],
    )

    _banner("wiring dependencies (review -> write, deploy -> review)")
    svc.add_dependency(review.id, write.id)
    svc.add_dependency(deploy.id, review.id)

    _banner("topological order")
    for t in svc.topological_order():
        print("  ", t)

    _banner("guard: completing 'deploy' before deps are done should fail")
    try:
        svc.complete(deploy.id)
    except Exception as exc:  # noqa: BLE001 - demo
        print(f"  blocked as expected -> {exc}")

    _banner("progressing work")
    svc.set_status(write.id, Status.IN_PROGRESS)
    svc.complete(write.id)
    svc.complete(review.id)
    svc.complete(deploy.id)

    _banner("recurring task: completing standup spawns tomorrow's")
    svc.complete(standup.id)

    _banner("query: high-priority active tasks")
    spec = ByPriority(Priority.HIGH) & ByStatus(Status.TODO, Status.IN_PROGRESS)
    for t in svc.find(spec, sort="due"):
        print("  ", t)

    _banner("query: overdue OR tagged #home")
    for t in svc.find(IsOverdue() | HasTag("home")):
        print("  ", t)

    _banner("search text 'design'")
    for t in svc.find(TextMatches("design")):
        print("  ", t)

    _banner("undo last 2 ops, then redo 1")
    print("  undid:", svc.undo())
    print("  undid:", svc.undo())
    print("  redid:", svc.redo())

    _banner("statistics")
    for line in svc.stats().as_lines():
        print("  ", line)

    _banner("active workload by tag")
    for tag, n in Analyzer.workload_by_tag(svc.all()).items():
        print(f"   #{tag}: {n}")

    return svc


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()

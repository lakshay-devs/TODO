"""Aggregations and reporting over a collection of tasks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .enums import Priority, Status
from .models import Tag, Task


@dataclass(frozen=True, slots=True)
class Stats:
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    overdue: int
    completion_rate: float
    top_tags: list[tuple[str, int]]

    def as_lines(self) -> list[str]:
        lines = [
            f"total tasks   : {self.total}",
            f"completion    : {self.completion_rate:.0%}",
            f"overdue       : {self.overdue}",
            "by status     : "
            + ", ".join(f"{k}={v}" for k, v in self.by_status.items()),
            "by priority   : "
            + ", ".join(f"{k}={v}" for k, v in self.by_priority.items()),
        ]
        if self.top_tags:
            lines.append(
                "top tags      : "
                + ", ".join(f"#{name}={n}" for name, n in self.top_tags)
            )
        return lines


class Analyzer:
    """Computes a Stats snapshot from any iterable of tasks."""

    def __init__(self, top_n_tags: int = 5) -> None:
        self.top_n_tags = top_n_tags

    def compute(self, tasks: Iterable[Task]) -> Stats:
        tasks = list(tasks)
        total = len(tasks)
        by_status = Counter(t.status.name for t in tasks)
        by_priority = Counter(t.priority.label for t in tasks)
        overdue = sum(1 for t in tasks if t.is_overdue)
        done = sum(1 for t in tasks if t.status is Status.DONE)
        rate = (done / total) if total else 0.0

        tag_counter: Counter[Tag] = Counter()
        for t in tasks:
            tag_counter.update(t.tags)
        top_tags = [(tag.name, n) for tag, n in tag_counter.most_common(self.top_n_tags)]

        return Stats(
            total=total,
            by_status={s.name: by_status.get(s.name, 0) for s in Status},
            by_priority={p.label: by_priority.get(p.label, 0) for p in Priority},
            overdue=overdue,
            completion_rate=rate,
            top_tags=top_tags,
        )

    @staticmethod
    def workload_by_tag(tasks: Iterable[Task]) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for t in tasks:
            if t.status.is_active:
                for tag in t.tags:
                    counter[tag.name] += 1
        return dict(counter.most_common())

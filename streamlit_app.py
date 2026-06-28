"""Streamlit UI for the todoapp engine.

Run with:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import streamlit as st

# Make the `src/` layout importable without an editable install.
SRC = Path(__file__).parent / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from todoapp.enums import Priority, RecurrenceUnit, Status
from todoapp.exceptions import TodoError
from todoapp.models import RecurrenceRule
from todoapp.persistence import FileTaskRepository
from todoapp.service import TodoService
from todoapp.specifications import (
    ByPriority,
    ByStatus,
    HasTag,
    IsOverdue,
    TextMatches,
)

DATA_FILE = Path(__file__).parent / "tasks.json"

STATUS_ICON = {
    Status.TODO: "⬜",
    Status.IN_PROGRESS: "🔄",
    Status.BLOCKED: "⛔",
    Status.DONE: "✅",
    Status.ARCHIVED: "📦",
}


# --- service wiring --------------------------------------------------------
@st.cache_resource
def get_service() -> TodoService:
    """One persistent service per server process (JSON-file backed)."""
    return TodoService(repo=FileTaskRepository(DATA_FILE))


svc = get_service()


def rerun() -> None:
    st.rerun()


# --- sidebar: create task --------------------------------------------------
def sidebar_add() -> None:
    st.sidebar.header("➕ Add task")
    with st.sidebar.form("add_task", clear_on_submit=True):
        title = st.text_input("Title")
        description = st.text_area("Description", height=80)
        priority = st.selectbox(
            "Priority",
            list(Priority),
            index=list(Priority).index(Priority.MEDIUM),
            format_func=lambda p: p.label,
        )
        has_due = st.checkbox("Has due date")
        due = st.date_input("Due", value=date.today()) if has_due else None
        tags_raw = st.text_input("Tags (comma separated)")
        recurs = st.checkbox("Recurring")
        rule = None
        if recurs:
            col_u, col_i = st.columns(2)
            unit = col_u.selectbox(
                "Every", list(RecurrenceUnit), format_func=lambda u: u.name.capitalize()
            )
            interval = col_i.number_input("Interval", min_value=1, value=1, step=1)
            rule = RecurrenceRule(unit, int(interval))

        if st.form_submit_button("Add", use_container_width=True):
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            try:
                svc.add(
                    title,
                    description=description,
                    priority=priority,
                    due=due,
                    tags=tags,
                    recurrence=rule,
                )
                st.sidebar.success(f"Added “{title}”")
                rerun()
            except TodoError as exc:
                st.sidebar.error(str(exc))


def sidebar_history() -> None:
    st.sidebar.header("↩️ History")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("Undo", use_container_width=True):
        try:
            name = svc.undo()
            st.sidebar.info(f"Undid {name}")
            rerun()
        except TodoError as exc:
            st.sidebar.warning(str(exc))
    if c2.button("Redo", use_container_width=True):
        try:
            name = svc.redo()
            st.sidebar.info(f"Redid {name}")
            rerun()
        except TodoError as exc:
            st.sidebar.warning(str(exc))


# --- filters ---------------------------------------------------------------
def build_filters():
    st.subheader("🔎 Filters")
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    statuses = c1.multiselect(
        "Status", list(Status), format_func=lambda s: s.name.replace("_", " ").title()
    )
    min_priority = c2.selectbox(
        "Min priority",
        [None, *list(Priority)],
        format_func=lambda p: "Any" if p is None else p.label,
    )
    tag = c3.text_input("Tag")
    overdue_only = c4.checkbox("Overdue only")
    c5, c6 = st.columns([3, 1])
    text = c5.text_input("Search text")
    sort = c6.selectbox("Sort", ["priority", "due", "created", "title", "status"])

    spec = None

    def chain(s):
        nonlocal spec
        spec = s if spec is None else spec & s

    if statuses:
        chain(ByStatus(*statuses))
    if min_priority is not None:
        chain(ByPriority(min_priority))
    if tag.strip():
        chain(HasTag(tag.strip()))
    if overdue_only:
        chain(IsOverdue())
    if text.strip():
        chain(TextMatches(text.strip()))
    return spec, sort


# --- task rendering --------------------------------------------------------
def render_task(task) -> None:
    icon = STATUS_ICON[task.status]
    overdue = " 🔴 OVERDUE" if task.is_overdue else ""
    due = f" · due {task.due}" if task.due else ""
    tags = " ".join(str(t) for t in sorted(task.tags))
    header = f"{icon} {task.priority.label[:4]:<4} {task.title}{due}{overdue}"

    with st.expander(header):
        if task.description:
            st.write(task.description)
        meta = [f"`{task.id}`", f"status: **{task.status.name}**"]
        if tags:
            meta.append(tags)
        if task.dependencies:
            meta.append(f"deps: {', '.join(sorted(task.dependencies))}")
        st.caption(" · ".join(meta))

        cols = st.columns(4)
        # status transition
        new_status = cols[0].selectbox(
            "Set status",
            list(Status),
            index=list(Status).index(task.status),
            key=f"st_{task.id}",
            format_func=lambda s: s.name.replace("_", " ").title(),
        )
        if cols[1].button("Apply", key=f"apply_{task.id}"):
            try:
                svc.set_status(task.id, new_status)
                rerun()
            except TodoError as exc:
                st.error(str(exc))
        if not task.is_done and cols[2].button("✅ Complete", key=f"done_{task.id}"):
            try:
                svc.complete(task.id)
                rerun()
            except TodoError as exc:
                st.error(str(exc))
        if cols[3].button("🗑️ Delete", key=f"del_{task.id}"):
            svc.delete(task.id)
            rerun()


# --- stats -----------------------------------------------------------------
def render_stats() -> None:
    s = svc.stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", s.total)
    c2.metric("Completion", f"{s.completion_rate:.0%}")
    c3.metric("Overdue", s.overdue)
    c4.metric("Done", s.by_status.get("DONE", 0))
    ca, cb = st.columns(2)
    ca.bar_chart(
        {k: v for k, v in s.by_status.items() if v}, x_label="status", y_label="count"
    )
    cb.bar_chart(
        {k: v for k, v in s.by_priority.items() if v},
        x_label="priority",
        y_label="count",
    )
    if s.top_tags:
        st.caption("Top tags: " + ", ".join(f"#{n}={c}" for n, c in s.top_tags))


# --- main ------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="TodoApp", page_icon="✅", layout="wide")
    st.title("✅ TodoApp")

    sidebar_add()
    sidebar_history()

    tab_tasks, tab_stats, tab_dag = st.tabs(["📋 Tasks", "📊 Stats", "🔗 Order"])

    with tab_tasks:
        spec, sort = build_filters()
        tasks = svc.find(spec, sort=sort)
        st.caption(f"{len(tasks)} task(s)")
        if not tasks:
            st.info("No tasks match. Add one from the sidebar.")
        for task in tasks:
            render_task(task)

    with tab_stats:
        render_stats()

    with tab_dag:
        st.subheader("Topological order (dependencies first)")
        try:
            for i, task in enumerate(svc.topological_order(), 1):
                st.write(f"{i}. {STATUS_ICON[task.status]} {task.title}  `{task.id}`")
        except TodoError as exc:
            st.error(f"Cannot order: {exc}")

        st.divider()
        st.subheader("Add dependency")
        all_tasks = svc.all()
        if len(all_tasks) >= 2:
            opts = {f"{t.title} ({t.id})": t.id for t in all_tasks}
            c1, c2 = st.columns(2)
            a = c1.selectbox("Task", list(opts), key="dep_a")
            b = c2.selectbox("depends on", list(opts), key="dep_b")
            if st.button("Link"):
                try:
                    svc.add_dependency(opts[a], opts[b])
                    st.success("Linked")
                    rerun()
                except TodoError as exc:
                    st.error(str(exc))
        else:
            st.info("Need at least 2 tasks to link dependencies.")


if __name__ == "__main__":
    main()

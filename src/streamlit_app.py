"""Streamlit UI for the todoapp engine.

Run with:  streamlit run src/streamlit_app.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import streamlit as st

# This file lives in `src/`, alongside the `todoapp` package.
SRC = Path(__file__).parent
if str(SRC) not in sys.path:
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

DATA_FILE = Path(__file__).parent.parent / "tasks.json"

STATUS_ICON = {
    Status.TODO: "⬜",
    Status.IN_PROGRESS: "🔄",
    Status.BLOCKED: "⛔",
    Status.DONE: "✅",
    Status.ARCHIVED: "📦",
}

# Accent colour per status / priority — drives the coloured pills + badges.
STATUS_COLOR = {
    Status.TODO: "#64748b",
    Status.IN_PROGRESS: "#2563eb",
    Status.BLOCKED: "#dc2626",
    Status.DONE: "#16a34a",
    Status.ARCHIVED: "#94a3b8",
}
PRIORITY_COLOR = {
    Priority.CRITICAL: "#dc2626",
    Priority.HIGH: "#ea580c",
    Priority.MEDIUM: "#2563eb",
    Priority.LOW: "#0891b2",
    Priority.TRIVIAL: "#94a3b8",
}


# --- service wiring --------------------------------------------------------
@st.cache_resource
def get_service() -> TodoService:
    """One persistent service per server process (JSON-file backed)."""
    return TodoService(repo=FileTaskRepository(DATA_FILE))


svc = get_service()


def rerun() -> None:
    st.rerun()


# --- styling ---------------------------------------------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
          .block-container { padding-top: 2rem; max-width: 1100px; }
          /* hero banner */
          .hero {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #d946ef 100%);
            padding: 1.4rem 1.6rem; border-radius: 16px; color: #fff;
            margin-bottom: 1.2rem; box-shadow: 0 8px 24px rgba(99,102,241,.25);
          }
          .hero h1 { margin: 0; font-size: 1.9rem; font-weight: 800; }
          .hero p  { margin: .25rem 0 0; opacity: .9; font-size: .95rem; }
          /* generic pill / badge */
          .pill {
            display: inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: .72rem; font-weight: 700; color: #fff; line-height: 1.5;
            margin-right: 6px; white-space: nowrap;
          }
          .badge {
            display: inline-block; padding: 2px 9px; border-radius: 8px;
            font-size: .72rem; font-weight: 600; line-height: 1.5; margin-right: 6px;
          }
          .tag {
            display: inline-block; padding: 1px 8px; border-radius: 999px;
            font-size: .7rem; background: #eef2ff; color: #4338ca;
            margin-right: 5px; font-weight: 600;
          }
          .ttl { font-size: 1.05rem; font-weight: 700; }
          .ttl-done { text-decoration: line-through; opacity: .55; }
          .muted { color: #94a3b8; font-size: .78rem; }
          /* task card container */
          div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
          }
          /* progress bar slimmer */
          .stProgress > div > div { height: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def due_badge(task) -> str:
    """Coloured due-date badge HTML, or empty string when no due date."""
    if task.due is None:
        return ""
    d = task.days_until_due
    if task.is_overdue:
        bg, fg, txt = "#fee2e2", "#b91c1c", f"⚠ Overdue · {task.due} ({-d}d)"
    elif d == 0:
        bg, fg, txt = "#fef9c3", "#a16207", f"Due today · {task.due}"
    elif d is not None and d <= 2:
        bg, fg, txt = "#fef9c3", "#a16207", f"Due soon · {task.due} ({d}d)"
    else:
        bg, fg, txt = "#f1f5f9", "#475569", f"Due {task.due} ({d}d)"
    return f'<span class="badge" style="background:{bg};color:{fg}">{txt}</span>'


# --- sidebar: create task --------------------------------------------------
def sidebar_add() -> None:
    st.sidebar.header("➕ Add task")
    with st.sidebar.form("add_task", clear_on_submit=True):
        title = st.text_input("Title", placeholder="What needs doing?")
        description = st.text_area("Description", height=80, placeholder="Optional details…")
        priority = st.select_slider(
            "Priority",
            options=list(Priority),
            value=Priority.MEDIUM,
            format_func=lambda p: p.label,
        )
        has_due = st.checkbox("Has due date")
        due = st.date_input("Due", value=date.today()) if has_due else None
        tags_raw = st.text_input("Tags", placeholder="work, urgent")
        recurs = st.checkbox("Recurring")
        rule = None
        if recurs:
            col_u, col_i = st.columns(2)
            unit = col_u.selectbox(
                "Every", list(RecurrenceUnit), format_func=lambda u: u.name.capitalize()
            )
            interval = col_i.number_input("Interval", min_value=1, value=1, step=1)
            rule = RecurrenceRule(unit, int(interval))

        if st.form_submit_button("Add task", use_container_width=True, type="primary"):
            tags = [t.strip() for t in tags_raw.replace(",", " ").split() if t.strip()]
            try:
                svc.add(
                    title,
                    description=description,
                    priority=priority,
                    due=due,
                    tags=tags,
                    recurrence=rule,
                )
                st.toast(f"Added “{title}”", icon="✅")
                rerun()
            except TodoError as exc:
                st.sidebar.error(str(exc))


def sidebar_history() -> None:
    st.sidebar.divider()
    st.sidebar.header("↩️ History")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("↶ Undo", use_container_width=True):
        try:
            st.toast(f"Undid {svc.undo()}", icon="↶")
            rerun()
        except TodoError as exc:
            st.sidebar.warning(str(exc))
    if c2.button("↷ Redo", use_container_width=True):
        try:
            st.toast(f"Redid {svc.redo()}", icon="↷")
            rerun()
        except TodoError as exc:
            st.sidebar.warning(str(exc))


# --- header dashboard ------------------------------------------------------
def render_hero() -> None:
    s = svc.stats()
    st.markdown(
        '<div class="hero"><h1>✅ TodoApp</h1>'
        "<p>Plan, track and complete — backed by an undo-able task engine.</p></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    active = s.by_status.get("TODO", 0) + s.by_status.get("IN_PROGRESS", 0)
    c1.metric("Total", s.total)
    c2.metric("Active", active)
    c3.metric("Done", s.by_status.get("DONE", 0))
    c4.metric("Overdue", s.overdue, delta=None if not s.overdue else "needs attention",
              delta_color="inverse")
    st.progress(s.completion_rate, text=f"{s.completion_rate:.0%} complete")


# --- filters ---------------------------------------------------------------
def build_filters():
    with st.expander("🔎 Filters & sort", expanded=False):
        c1, c2, c3 = st.columns([2, 2, 1])
        statuses = c1.multiselect(
            "Status", list(Status),
            format_func=lambda s: s.name.replace("_", " ").title(),
        )
        min_priority = c2.selectbox(
            "Min priority", [None, *list(Priority)],
            format_func=lambda p: "Any" if p is None else p.label,
        )
        overdue_only = c3.checkbox("Overdue", value=False)
        c4, c5, c6 = st.columns([2, 2, 1])
        tag = c4.text_input("Tag", placeholder="work")
        text = c5.text_input("Search", placeholder="title or description")
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
    with st.container(border=True):
        top, actions = st.columns([5, 1])
        with top:
            pc = PRIORITY_COLOR[task.priority]
            sc = STATUS_COLOR[task.status]
            ttl_cls = "ttl ttl-done" if task.is_done else "ttl"
            badges = (
                f'<span class="pill" style="background:{sc}">'
                f"{STATUS_ICON[task.status]} {task.status.name.replace('_',' ').title()}</span>"
                f'<span class="pill" style="background:{pc}">{task.priority.label}</span>'
                + due_badge(task)
            )
            tags = "".join(f'<span class="tag">{t}</span>' for t in sorted(str(x) for x in task.tags))
            st.markdown(
                f'<div class="{ttl_cls}">{task.title}</div>{badges}'
                + (f'<div style="margin-top:6px">{tags}</div>' if tags else ""),
                unsafe_allow_html=True,
            )
            if task.description:
                st.markdown(f'<div style="margin-top:6px">{task.description}</div>',
                            unsafe_allow_html=True)
            meta = f"<code>{task.id}</code>"
            if task.dependencies:
                meta += f" · depends on {', '.join(f'<code>{d}</code>' for d in sorted(task.dependencies))}"
            st.markdown(f'<div class="muted" style="margin-top:6px">{meta}</div>',
                        unsafe_allow_html=True)

        with actions:
            with st.popover("⚙", use_container_width=True):
                if not task.is_done and st.button("✅ Complete", key=f"done_{task.id}",
                                                  use_container_width=True):
                    _try(svc.complete, task.id)
                new_status = st.selectbox(
                    "Set status", list(Status),
                    index=list(Status).index(task.status),
                    key=f"st_{task.id}",
                    format_func=lambda s: s.name.replace("_", " ").title(),
                )
                if st.button("Apply status", key=f"apply_{task.id}",
                             use_container_width=True):
                    _try(svc.set_status, task.id, new_status)
                if st.button("🗑 Delete", key=f"del_{task.id}",
                             use_container_width=True):
                    _try(svc.delete, task.id)


def _try(fn, *args) -> None:
    """Run a mutating service call, surface TodoError as a toast, then rerun."""
    try:
        fn(*args)
        rerun()
    except TodoError as exc:
        st.toast(str(exc), icon="⚠️")


# --- stats -----------------------------------------------------------------
def render_stats() -> None:
    s = svc.stats()
    st.subheader("📊 Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", s.total)
    c2.metric("Completion", f"{s.completion_rate:.0%}")
    c3.metric("Overdue", s.overdue)
    c4.metric("Done", s.by_status.get("DONE", 0))
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.caption("By status")
        st.bar_chart({k: v for k, v in s.by_status.items() if v},
                     x_label="status", y_label="count", color="#6366f1")
    with cb:
        st.caption("By priority")
        st.bar_chart({k: v for k, v in s.by_priority.items() if v},
                     x_label="priority", y_label="count", color="#d946ef")
    if s.top_tags:
        st.divider()
        st.caption("Top tags")
        st.markdown(
            " ".join(f'<span class="tag">#{n} · {c}</span>' for n, c in s.top_tags),
            unsafe_allow_html=True,
        )


# --- dependency tab --------------------------------------------------------
def render_order() -> None:
    st.subheader("🔗 Execution order")
    st.caption("Tasks listed so every dependency comes before what needs it.")
    try:
        order = svc.topological_order()
        if not order:
            st.info("No tasks yet.")
        for i, task in enumerate(order, 1):
            st.markdown(
                f'**{i}.** {STATUS_ICON[task.status]} {task.title} '
                f'<span class="muted">`{task.id}`</span>',
                unsafe_allow_html=True,
            )
    except TodoError as exc:
        st.error(f"Cannot order — cycle detected: {exc}")

    st.divider()
    st.subheader("Add dependency")
    all_tasks = svc.all()
    if len(all_tasks) >= 2:
        opts = {f"{t.title} ({t.id})": t.id for t in all_tasks}
        c1, c2 = st.columns(2)
        a = c1.selectbox("Task", list(opts), key="dep_a")
        b = c2.selectbox("depends on", list(opts), key="dep_b")
        if st.button("🔗 Link", type="primary"):
            try:
                svc.add_dependency(opts[a], opts[b])
                st.toast("Linked", icon="🔗")
                rerun()
            except TodoError as exc:
                st.error(str(exc))
    else:
        st.info("Need at least 2 tasks to link dependencies.")


# --- main ------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="TodoApp", page_icon="✅", layout="wide")
    inject_css()
    render_hero()

    sidebar_add()
    sidebar_history()

    tab_tasks, tab_stats, tab_dag = st.tabs(["📋 Tasks", "📊 Stats", "🔗 Order"])

    with tab_tasks:
        spec, sort = build_filters()
        tasks = svc.find(spec, sort=sort)
        st.caption(f"Showing {len(tasks)} task(s)")
        if not tasks:
            st.info("🗒️ Nothing here yet — add a task from the sidebar to get started.")
        for task in tasks:
            render_task(task)

    with tab_stats:
        render_stats()

    with tab_dag:
        render_order()


if __name__ == "__main__":
    main()

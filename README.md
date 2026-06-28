# todoapp

In-memory todo engine. Pure stdlib. Built with [uv](https://docs.astral.sh/uv/).

## Run

```bash
uv run todoapp          # scripted end-to-end demo
uv run python -m todoapp
uv run pytest -q        # 14 tests
```

## Library use

```python
from datetime import date, timedelta
from todoapp import TodoService, Priority, Status, ByPriority, ByStatus, HasTag

svc = TodoService()
a = svc.add("Write doc", priority="high", due=date.today() + timedelta(days=2), tags=["work"])
b = svc.add("Review doc", priority=Priority.MEDIUM, tags=["work"])

svc.add_dependency(b.id, a.id)        # review depends on write
svc.complete(a.id)
svc.complete(b.id)                    # allowed only after deps done

hot = svc.find(ByPriority(Priority.HIGH) & ByStatus(Status.TODO), sort="due")
print(svc.stats().as_lines())
svc.undo(); svc.redo()
```

## Architecture

| Module             | Responsibility                                              |
|--------------------|-------------------------------------------------------------|
| `enums.py`         | `Priority`, `Status`, `RecurrenceUnit`, transition rules    |
| `exceptions.py`    | Domain error hierarchy (`TodoError` root)                   |
| `models.py`        | `Tag`, `RecurrenceRule`, `Task` aggregate root              |
| `repository.py`    | `TaskRepository` port + `InMemoryTaskRepository`            |
| `specifications.py`| Composable filters (`&`, `\|`, `~`) — Specification pattern  |
| `sorting.py`       | Named sort strategies                                       |
| `commands.py`      | Command pattern + `CommandInvoker` undo/redo, `MacroCommand`|
| `events.py`        | `EventBus` observer pattern                                 |
| `analytics.py`     | `Analyzer` → `Stats` aggregations                           |
| `service.py`       | `TodoService` facade; dependency DAG + topological sort     |
| `cli.py`           | Scripted demo                                               |

## Patterns used

- **Repository / port-adapter** — swap storage without touching logic
- **Specification** — declarative, composable queries
- **Command + Invoker** — full undo/redo, atomic macro with rollback
- **Observer** — synchronous event bus
- **State machine** — guarded status transitions
- **Strategy** — pluggable sort keys
- **DAG** — dependency cycle detection + Kahn topological order
- **Recurrence** — completing a recurring task spawns its next occurrence

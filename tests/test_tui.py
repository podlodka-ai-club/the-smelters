from __future__ import annotations

from tui import TASK_COLUMNS, load_task_rows
from src.tracker import Tracker


def test_load_task_rows_includes_project_column(tmp_db) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(
        title="Fix startup crash",
        project="demo_app",
        spec_path="tasks/example.md",
    )
    tracker.set_status(task_id, "review")
    tracker.increment_attempts(task_id)

    rows = load_task_rows(tmp_db)

    assert TASK_COLUMNS == ("id", "project", "status", "attempts", "title")
    assert rows == [("1", "demo_app", "review", "1", "Fix startup crash")]

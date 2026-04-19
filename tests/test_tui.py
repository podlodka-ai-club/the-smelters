from __future__ import annotations

from pathlib import Path

import pytest

from src.tracker import Tracker
from tui import load_task_rows, main


def test_load_task_rows_returns_task_numbers_in_order(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=9, title="later", spec_path="tasks/DemoApp/9-later.md")
    tracker.insert_task(task_number=2, title="earlier", spec_path="tasks/DemoApp/2-earlier.md")

    rows = load_task_rows(tmp_db)

    assert rows == [("2", "ready", "0", "earlier"), ("9", "ready", "0", "later")]


def test_main_requires_project() -> None:
    with pytest.raises(SystemExit):
        main([])

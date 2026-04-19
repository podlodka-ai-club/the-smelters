from __future__ import annotations

from pathlib import Path

import pytest

from src.tracker import TaskNotFound, Tracker


def test_insert_and_get(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(
        task_number=7,
        title="divide by zero",
        spec_path="tasks/python_fixture/7-divide-by-zero.md",
    )
    row = tracker.get_task(task_id)
    assert row.id == task_id
    assert row.task_number == 7
    assert row.status == "ready"
    assert row.attempts == 0


def test_claim_next_ready_returns_none_when_empty(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    assert tracker.claim_next_ready_task() is None


def test_claim_next_ready_atomically_sets_running(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=9, title="a", spec_path="tasks/alpha/9-a.md")
    tracker.insert_task(task_number=2, title="b", spec_path="tasks/beta/2-b.md")
    claimed = tracker.claim_next_ready_task()
    assert claimed is not None
    assert claimed.title == "b"
    assert claimed.task_number == 2
    assert claimed.status == "running"
    all_tasks = list(tracker.list_tasks())
    assert [(task.task_number, task.status) for task in all_tasks] == [(2, "running"), (9, "ready")]


def test_claim_next_ready_can_filter_by_project(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=1, title="a", spec_path="tasks/alpha/1-a.md")
    tracker.insert_task(task_number=2, title="b", spec_path="tasks/beta/2-b.md")

    claimed = tracker.claim_next_ready_task(project="beta")

    assert claimed is not None
    assert claimed.title == "b"
    assert claimed.task_number == 2
    assert claimed.status == "running"


def test_claim_next_ready_can_filter_by_task_id(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=7, title="a", spec_path="tasks/alpha/7-a.md")
    tracker.insert_task(task_number=2, title="b", spec_path="tasks/beta/2-b.md")

    claimed = tracker.claim_next_ready_task(task_id=2)

    assert claimed is not None
    assert claimed.task_number == 2
    assert claimed.title == "b"
    assert claimed.status == "running"


def test_set_status_updates_row(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(task_number=1, title="a", spec_path="tasks/a.md")
    tracker.set_status(task_id, "review")
    assert tracker.get_task(task_id).status == "review"


def test_increment_attempts(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(task_number=1, title="a", spec_path="tasks/a.md")
    tracker.increment_attempts(task_id)
    tracker.increment_attempts(task_id)
    assert tracker.get_task(task_id).attempts == 2


def test_save_review_notes_and_read_back(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(task_number=1, title="a", spec_path="tasks/a.md")
    tracker.save_review_notes(task_id, "don't hardcode")
    assert tracker.get_task(task_id).review_notes == "don't hardcode"


def test_set_worktree_persists(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(task_number=1, title="a", spec_path="tasks/a.md")
    tracker.set_worktree(task_id, worktree="worktrees/task-1", branch="task-1")
    row = tracker.get_task(task_id)
    assert row.worktree == "worktrees/task-1"
    assert row.branch == "task-1"


def test_get_task_raises_on_unknown_id(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    with pytest.raises(TaskNotFound):
        tracker.get_task(999)


def test_reset_stuck_tasks_sets_running_and_review_back_to_ready(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_a = tracker.insert_task(task_number=1, title="a", spec_path="tasks/a.md")
    task_b = tracker.insert_task(task_number=2, title="b", spec_path="tasks/b.md")
    task_c = tracker.insert_task(task_number=3, title="c", spec_path="tasks/c.md")
    tracker.set_status(task_a, "running")
    tracker.set_status(task_b, "review")
    tracker.set_status(task_c, "closed")
    tracker.reset_stuck_tasks()
    assert tracker.get_task(task_a).status == "ready"
    assert tracker.get_task(task_b).status == "ready"
    assert tracker.get_task(task_c).status == "closed"

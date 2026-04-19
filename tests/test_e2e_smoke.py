"""One real task end-to-end through the real Coder and Reviewer agents."""
from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from orchestrator import Orchestrator
from seed import seed
from src.tracker import Tracker


@pytest.mark.live
@pytest.mark.asyncio
async def test_solve_task_001_with_real_agents(tmp_path: Path) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    source = Path(__file__).parent.parent / "projects" / "python_fixture"
    destination = tmp_path / "projects" / "python_fixture"
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__", ".venv"),
    )

    if (destination / ".git").exists():
        shutil.rmtree(destination / ".git")

    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    shutil.copy2(
        Path(__file__).parent.parent / "tasks" / "1-divide-by-zero.md",
        tasks_root / "1-divide-by-zero.md",
    )

    db_path = tmp_path / "tasks.db"
    events_path = tmp_path / "events.jsonl"

    seed(db_path, tasks_root=tasks_root, projects_root=tmp_path / "projects")
    os.environ["TRACKER_DB"] = str(db_path)

    orchestrator = Orchestrator(
        tracker=Tracker(db_path),
        events_path=events_path,
        projects_root=tmp_path / "projects",
        tasks_root=tasks_root,
        worktrees_root=tmp_path / "wt",
        max_attempts=2,
        coder_timeout=240,
        reviewer_timeout=120,
    )
    await orchestrator.run_until_empty()

    statuses = {task.id: task.status for task in Tracker(db_path).list_tasks()}
    assert any(status == "closed" for status in statuses.values()), f"no task closed: {statuses}"

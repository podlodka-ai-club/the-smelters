"""One real task end-to-end through the real Coder and Reviewer agents."""
from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from orchestrator import Orchestrator
from seed import seed
from src.runtime_paths import project_runtime_paths
from src.tracker import Tracker


@pytest.mark.live
@pytest.mark.asyncio
async def test_solve_task_001_with_real_agents(tmp_path: Path) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    source = Path(__file__).parent.parent.parent / "projects" / "python_fixture"
    destination = tmp_path / "projects" / "python_fixture"
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__", ".venv"),
    )

    if (destination / ".git").exists():
        shutil.rmtree(destination / ".git")

    tasks_root = tmp_path / "tasks"
    (tasks_root / "python_fixture").mkdir(parents=True)
    shutil.copy2(
        Path(__file__).parent.parent.parent / "tasks" / "python_fixture" / "1-divide-by-zero.md",
        tasks_root / "python_fixture" / "1-divide-by-zero.md",
    )

    runtime = project_runtime_paths(tmp_path, "python_fixture")
    runtime.db_path.parent.mkdir(parents=True, exist_ok=True)

    seed(runtime.db_path, project="python_fixture", tasks_root=tasks_root, projects_root=tmp_path / "projects")
    os.environ["TRACKER_DB"] = str(runtime.db_path)

    orchestrator = Orchestrator(
        tracker=Tracker(runtime.db_path),
        project="python_fixture",
        root_path=tmp_path,
        events_path=runtime.events_path,
        projects_root=tmp_path / "projects",
        tasks_root=tasks_root,
        worktrees_root=runtime.worktrees_path,
        max_attempts=2,
        coder_timeout=240,
        reviewer_timeout=120,
    )
    await orchestrator.run_until_empty()

    statuses = {task.task_number: task.status for task in Tracker(runtime.db_path).list_tasks()}
    assert any(status == "closed" for status in statuses.values()), f"no task closed: {statuses}"

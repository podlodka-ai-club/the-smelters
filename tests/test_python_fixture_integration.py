from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from orchestrator import Orchestrator
from seed import seed
from src.tracker import Tracker



@pytest.mark.asyncio
async def test_project_scoped_tasks_drive_python_fixture_from_projects(tmp_path: Path) -> None:
    source_project = Path(__file__).parent.parent / "projects" / "python_fixture"
    source_tasks = Path(__file__).parent.parent / "tasks" / "python_fixture"

    projects_root = tmp_path / "projects"
    tasks_root = tmp_path / "tasks"
    project_repo = projects_root / "python_fixture"
    shutil.copytree(
        source_project,
        project_repo,
        ignore=shutil.ignore_patterns(".pytest_cache", "__pycache__", ".venv", ".DS_Store"),
    )
    shutil.copytree(source_tasks, tasks_root / "python_fixture")

    db_path = tmp_path / "tasks.db"
    events_path = tmp_path / "events.jsonl"
    seed(db_path, tasks_root=tasks_root, projects_root=projects_root)

    tracker = Tracker(db_path)
    tracker.init_schema()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("FAKE_CODER", "ok")
        monkeypatch.setenv("FAKE_REVIEWER", "approve")
        orchestrator = Orchestrator(
            tracker=tracker,
            events_path=events_path,
            projects_root=projects_root,
            tasks_root=tasks_root,
            worktrees_root=tmp_path / "wt",
            coder_role="fake_coder",
            reviewer_role="fake_reviewer",
            max_attempts=2,
            coder_timeout=10,
            reviewer_timeout=10,
        )
        await orchestrator.run_until_empty()

    rows = list(Tracker(db_path).list_tasks())
    assert len(rows) == 5
    assert {row.project for row in rows} == {"python_fixture"}
    assert {row.status for row in rows} == {"closed"}

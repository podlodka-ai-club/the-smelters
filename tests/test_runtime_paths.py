from __future__ import annotations

from pathlib import Path

from src.runtime_paths import infer_project_from_tracker_db, project_runtime_paths


def test_project_runtime_paths_resolve_all_locations(tmp_path: Path) -> None:
    paths = project_runtime_paths(tmp_path, "DemoApp")

    assert paths.project == "DemoApp"
    assert paths.repo_path == tmp_path / "projects" / "DemoApp"
    assert paths.tasks_path == tmp_path / "tasks" / "DemoApp"
    assert paths.db_path == tmp_path / "database" / "DemoApp" / "tasks.db"
    assert paths.events_path == tmp_path / "database" / "DemoApp" / "events.jsonl"
    assert paths.worktrees_path == tmp_path / "worktrees" / "DemoApp"


def test_infer_project_from_tracker_db(tmp_path: Path) -> None:
    db = tmp_path / "database" / "FooProj" / "tasks.db"
    db.parent.mkdir(parents=True)
    assert infer_project_from_tracker_db(db) == "FooProj"
    assert infer_project_from_tracker_db(tmp_path / "tasks.db") is None

from __future__ import annotations

from pathlib import Path

import pytest

from seed import _task_number_from_filename, main, seed
from src.tracker import Tracker


def test_main_requires_project() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_task_number_is_parsed_from_filename() -> None:
    assert _task_number_from_filename(Path("7-share-download.md")) == 7


def test_seed_rejects_invalid_filename_prefix(tmp_path: Path, tmp_db: Path) -> None:
    tasks_root = tmp_path / "tasks"
    projects_root = tmp_path / "projects"
    (tasks_root / "DemoApp").mkdir(parents=True)
    (projects_root / "DemoApp").mkdir(parents=True)
    (tasks_root / "DemoApp" / "share-download.md").write_text(
        "Project: DemoApp\n\n# Share Download\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="task filename must start with an integer prefix"):
        seed(tmp_db, project="DemoApp", tasks_root=tasks_root, projects_root=projects_root)


def test_seed_reads_only_selected_project(tmp_path: Path, tmp_db: Path) -> None:
    tasks_root = tmp_path / "tasks"
    projects_root = tmp_path / "projects"
    (tasks_root / "DemoApp").mkdir(parents=True)
    (tasks_root / "python_fixture").mkdir(parents=True)
    (projects_root / "DemoApp").mkdir(parents=True)
    (projects_root / "python_fixture").mkdir(parents=True)
    (tasks_root / "DemoApp" / "7-share-download.md").write_text(
        "Project: DemoApp\n\n# Share Download\n",
        encoding="utf-8",
    )
    (tasks_root / "python_fixture" / "1-divide-by-zero.md").write_text(
        "Project: python_fixture\n\n# Divide By Zero\n",
        encoding="utf-8",
    )

    seed(tmp_db, project="DemoApp", tasks_root=tasks_root, projects_root=projects_root)

    rows = list(Tracker(tmp_db).list_tasks())
    assert len(rows) == 1
    assert rows[0].task_number == 7
    assert rows[0].title == "Share Download"
    assert rows[0].spec_path == "tasks/DemoApp/7-share-download.md"

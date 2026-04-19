from __future__ import annotations

from pathlib import Path

from src.project_profile import detect_project_profile
from seed import seed
from src.tracker import Tracker


def test_detect_python_profile_from_pyproject(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    profile = detect_project_profile(repo)

    assert profile.name == "python"
    assert profile.default_test_command == "pytest"
    assert "pytest" in profile.coder_verification


def test_detect_android_profile_from_gradle_markers(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    app_dir = repo / "app"
    app_dir.mkdir(parents=True)
    (repo / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "settings.gradle.kts").write_text("rootProject.name = \"demo\"\n", encoding="utf-8")
    (app_dir / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")

    profile = detect_project_profile(repo)

    assert profile.name == "android"
    assert profile.default_test_command == "./gradlew testDebugUnitTest"
    assert "./gradlew assembleDebug" in profile.reviewer_verification


def test_seed_reads_nested_project_tasks_and_task_number(tmp_path: Path, tmp_db: Path) -> None:
    tasks_root = tmp_path / "tasks"
    projects_root = tmp_path / "projects"
    repo = projects_root / "android_demo"
    project_tasks = tasks_root / "android_demo"
    project_tasks.mkdir(parents=True)
    repo.mkdir(parents=True)
    (repo / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "settings.gradle.kts").write_text("rootProject.name = \"demo\"\n", encoding="utf-8")
    (project_tasks / "1-fix-crash.md").write_text(
        "Project: android_demo\n\n# Fix startup crash\n\n## Failing test\nmanual\n",
        encoding="utf-8",
    )

    import subprocess

    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    seed(tmp_db, project="android_demo", tasks_root=tasks_root, projects_root=projects_root)

    tracker = Tracker(tmp_db)
    rows = list(tracker.list_tasks())
    assert len(rows) == 1
    assert rows[0].task_number == 1
    assert rows[0].title == "Fix startup crash"
    assert rows[0].spec_path == "tasks/android_demo/1-fix-crash.md"


def test_seed_accepts_project_directory_without_git_repo(tmp_path: Path, tmp_db: Path) -> None:
    tasks_root = tmp_path / "tasks"
    projects_root = tmp_path / "projects"
    project_dir = projects_root / "plain_python"
    project_tasks = tasks_root / "plain_python"
    project_tasks.mkdir(parents=True)
    project_dir.mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text("[project]\nname='plain-python'\n", encoding="utf-8")
    (project_tasks / "1-fix-bug.md").write_text(
        "Project: plain_python\n\n# Fix plain project bug\n",
        encoding="utf-8",
    )

    seed(tmp_db, project="plain_python", tasks_root=tasks_root, projects_root=projects_root)

    rows = list(Tracker(tmp_db).list_tasks())
    assert len(rows) == 1
    assert rows[0].task_number == 1
    assert rows[0].spec_path == "tasks/plain_python/1-fix-bug.md"

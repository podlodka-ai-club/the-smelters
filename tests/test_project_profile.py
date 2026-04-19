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


def test_seed_reads_root_tasks_and_project_reference(tmp_path: Path, tmp_db: Path) -> None:
    tasks_root = tmp_path / "tasks"
    projects_root = tmp_path / "projects"
    repo = projects_root / "android_demo"
    tasks_root.mkdir()
    repo.mkdir(parents=True)
    (repo / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / "settings.gradle.kts").write_text("rootProject.name = \"demo\"\n", encoding="utf-8")
    (tasks_root / "001_fix_crash.md").write_text(
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

    seed(tmp_db, tasks_root=tasks_root, projects_root=projects_root)

    tracker = Tracker(tmp_db)
    rows = list(tracker.list_tasks())
    assert len(rows) == 1
    assert rows[0].title == "Fix startup crash"
    assert rows[0].project == "android_demo"

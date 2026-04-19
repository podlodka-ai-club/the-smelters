from __future__ import annotations

from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a fresh SQLite file inside tmp_path."""
    return tmp_path / "tasks.db"


@pytest.fixture
def tmp_events(tmp_path: Path) -> Path:
    """Return a path to a fresh events.jsonl inside tmp_path."""
    return tmp_path / "events.jsonl"


@pytest.fixture
def tmp_target_repo(tmp_path: Path) -> Path:
    """Return a path to an initialised empty git repo."""
    repo = tmp_path / "target_repo"
    repo.mkdir()
    subprocess.run(
        ["git", "-C", str(repo), "init", "-b", "main"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@test"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "test"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return repo

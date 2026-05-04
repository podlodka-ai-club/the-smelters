from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from src.smelters_review_context import resolve_smelters_review_context


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "repo": "podlodka-ai-club/the-smelters",
        "base_branch": "main",
        "head_branch": None,
        "pr_title": None,
        "pr_body_file": None,
        "github_token_env": "GITHUB_TOKEN",
        "task_context_mode": "inline",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_resolve_context_normalizes_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    repo = tmp_path / "repo"
    (repo / "projects" / "DemoApp").mkdir(parents=True)
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    context = resolve_smelters_review_context(
        _args(repo="  podlodka-ai-club/the-smelters  ", pr_title="  title "),
        task_path=Path("tasks/the-smelters/001.md"),
        task_markdown="# task",
        project_path=Path("projects/DemoApp"),
    )
    assert context.repo == "podlodka-ai-club/the-smelters"
    assert context.pr_title == "title"
    assert context.task_path.endswith("tasks/the-smelters/001.md")
    assert context.task_markdown == "# task"
    assert context.project_scope_posix == "projects/DemoApp"


def test_resolve_context_rejects_invalid_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "DemoApp").mkdir(parents=True)
    with pytest.raises(SystemExit, match="Expected format: owner/name"):
        resolve_smelters_review_context(
            _args(repo="bad"),
            task_path=Path("tasks/the-smelters/001.md"),
            task_markdown="x",
            project_path=Path("projects/DemoApp"),
        )


def test_resolve_context_requires_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    monkeypatch.setattr("src.github_auth.fill_github_token_from_cli", lambda _name: False)
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects" / "DemoApp").mkdir(parents=True)
    with pytest.raises(SystemExit, match="GitHub authentication required"):
        resolve_smelters_review_context(
            _args(github_token_env="MISSING_TOKEN"),
            task_path=Path("tasks/the-smelters/001.md"),
            task_markdown="x",
            project_path=Path("projects/DemoApp"),
        )


def test_resolve_context_rejects_project_outside_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    repo = tmp_path / "repo"
    (repo / "projects" / "DemoApp").mkdir(parents=True)
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    outside = tmp_path / "outside_project"
    outside.mkdir()
    with pytest.raises(SystemExit, match="not under the git repository"):
        resolve_smelters_review_context(
            _args(),
            task_path=Path("tasks/x.md"),
            task_markdown="x",
            project_path=outside,
        )

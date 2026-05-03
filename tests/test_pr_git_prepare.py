from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agno_tools.pr_create_step import prepare_scoped_git_for_pr
from src.smelters_review_context import SmeltersReviewContext


def _git_config(repo: Path) -> None:
    subprocess.run(["git", "config", "user.email", "t@e.co"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)


def _ctx(scope: str = "projects/DemoApp", **kw: object) -> SmeltersReviewContext:
    defaults: dict[str, object] = {
        "repo": "o/r",
        "base_branch": "main",
        "head_branch": "feat/smelters-test",
        "pr_title": "Scoped PR",
        "pr_body_file": None,
        "github_token_env": "GITHUB_TOKEN",
        "task_context_mode": "inline",
        "task_path": "tasks/x.md",
        "task_markdown": "# x",
        "project_scope_posix": scope,
    }
    defaults.update(kw)
    return SmeltersReviewContext(**defaults)  # type: ignore[arg-type]


def test_prepare_scoped_git_commits_only_scope_and_pushes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

    work = tmp_path / "work"
    (work / "projects" / "DemoApp").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=work, check=True, capture_output=True)
    _git_config(work)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=work, check=True, capture_output=True)
    (work / "projects" / "DemoApp" / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "projects/DemoApp/a.txt"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=work, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=work, check=True, capture_output=True)

    (work / "projects" / "DemoApp" / "a.txt").write_text("b\n")
    monkeypatch.chdir(work)

    ok, err, head = prepare_scoped_git_for_pr(_ctx(head_branch="feat/scope-only"))
    assert ok is True, err
    assert err is None
    assert head == "feat/scope-only"

    show = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    )
    names = [ln.strip() for ln in show.stdout.splitlines() if ln.strip()]
    assert names == ["projects/DemoApp/a.txt"]

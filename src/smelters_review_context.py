from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.smelters_cli_validation import validate_smelters_pr_context


def _git_repo_root(*, git_cwd: Path | None = None) -> Path:
    cwd = git_cwd or Path.cwd()
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        msg = (completed.stderr or completed.stdout or "").strip() or "unknown error"
        sys.exit(
            "ERROR: smelters PR flow must run inside a git checkout.\n"
            f"  git rev-parse --show-toplevel failed: {msg}"
        )
    return Path(completed.stdout.strip()).resolve()


def _project_scope_posix(project_path: Path, *, git_cwd: Path | None = None) -> str:
    """Path of the Gradle project directory relative to the git root (POSIX, no trailing slash)."""
    root = _git_repo_root(git_cwd=git_cwd)
    base = git_cwd or Path.cwd()
    project_abs = (base / project_path).resolve()
    try:
        rel = project_abs.relative_to(root)
    except ValueError:
        sys.exit(
            f"ERROR: project path {project_path} is not under the git repository root {root}.\n"
            "  Run the orchestrator from the repo (or pass --project under that root)."
        )
    return rel.as_posix()


@dataclass(frozen=True)
class SmeltersReviewContext:
    repo: str
    base_branch: str
    head_branch: str | None
    pr_title: str | None
    pr_body_file: str | None
    github_token_env: str
    task_context_mode: str
    task_path: str
    task_markdown: str
    project_scope_posix: str


def resolve_smelters_review_context(
    args: argparse.Namespace,
    *,
    task_path: Path,
    task_markdown: str,
    project_path: Path,
) -> SmeltersReviewContext:
    """Validate and normalize smelters review inputs once per run."""
    validate_smelters_pr_context(args)
    scope = _project_scope_posix(project_path)
    return SmeltersReviewContext(
        repo=args.repo.strip(),
        base_branch=(args.base_branch or "main").strip(),
        head_branch=(args.head_branch or "").strip() or None,
        pr_title=(args.pr_title or "").strip() or None,
        pr_body_file=(args.pr_body_file or "").strip() or None,
        github_token_env=args.github_token_env.strip(),
        task_context_mode=args.task_context_mode.strip(),
        task_path=str(task_path),
        task_markdown=task_markdown,
        project_scope_posix=scope,
    )

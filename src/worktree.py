from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from src.runtime_paths import infer_project_from_tracker_db, project_runtime_paths
from src.tracker import Tracker


COPY_IGNORE_PATTERNS = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", ".venv", ".DS_Store")


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{details}") from exc


def _init_task_repo(worktree_path: Path, branch: str) -> None:
    _run(["git", "-C", str(worktree_path), "init", "-b", "main"])
    _run(["git", "-C", str(worktree_path), "config", "user.email", "task@local"])
    _run(["git", "-C", str(worktree_path), "config", "user.name", "task-runner"])
    _run(["git", "-C", str(worktree_path), "add", "-A"])
    _run(
        [
            "git",
            "-C",
            str(worktree_path),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "snapshot",
        ]
    )
    _run(["git", "-C", str(worktree_path), "checkout", "-b", branch])


def _agent_workdir_is_valid(path: Path, *, repo_path: Path, worktrees_path: Path) -> bool:
    """True only for directories under ``worktrees/<project>/`` (never ``projects/<project>``)."""
    if not path.exists() or not path.is_dir():
        return False
    try:
        resolved = path.resolve()
        if resolved == repo_path.resolve():
            return False
        resolved.relative_to(worktrees_path.resolve())
        return True
    except (OSError, ValueError):
        return False


def ensure_task_worktree_dir(
    *,
    repo_root: Path,
    tracker: Tracker,
    task_id: int,
    db_path: Path,
    project: str | None = None,
) -> tuple[Path, bool]:
    """
    Return the directory agents must use for this task.

    The canonical tree at ``projects/<project>`` is only a copy source; agent edits
    must live under ``worktrees/<project>/task-<N>``. If SQLite points at the
    canonical path or anywhere else outside the task worktrees tree, this creates
    (or reuses) the proper sandbox and updates the tracker.

    Returns ``(path, did_update_db)`` where ``did_update_db`` is True if ``set_worktree`` ran.
    """
    task = tracker.get_task(task_id)
    resolved_project = (
        (project or "").strip()
        or infer_project_from_tracker_db(db_path)
        or os.environ.get("TRACKER_PROJECT", "").strip()
    )
    if not resolved_project:
        raise RuntimeError(
            "Cannot resolve task sandbox: set TRACKER_DB under database/<Project>/tasks.db, "
            "pass project= to ensure_task_worktree_dir, or set TRACKER_PROJECT."
        )
    runtime = project_runtime_paths(repo_root, resolved_project)
    repo_path = runtime.repo_path
    worktrees_path = runtime.worktrees_path
    if not repo_path.is_dir():
        raise RuntimeError(f"Canonical project copy is missing: {repo_path}")

    if task.worktree:
        current = Path(task.worktree).expanduser()
        if _agent_workdir_is_valid(current, repo_path=repo_path, worktrees_path=worktrees_path):
            return current.resolve(), False

    worktree_path = create_worktree(
        repo_path,
        task_id=task.task_number,
        worktrees_root=worktrees_path,
    )
    tracker.set_worktree(
        task_id,
        worktree=str(worktree_path),
        branch=f"task-{task.task_number}",
    )
    return worktree_path, True


def create_worktree(repo: Path, *, task_id: int, worktrees_root: Path) -> Path:
    branch = f"task-{task_id}"
    worktree_path = worktrees_root / branch
    worktrees_root.mkdir(parents=True, exist_ok=True)

    if worktree_path.exists():
        return worktree_path

    shutil.copytree(repo, worktree_path, ignore=COPY_IGNORE_PATTERNS)
    _init_task_repo(worktree_path, branch)
    return worktree_path


def remove_worktree(repo: Path, worktree_path: Path, *, branch: str | None = None) -> None:
    del repo, branch
    if worktree_path.exists():
        shutil.rmtree(worktree_path)


def diff_vs_main(worktree_path: Path) -> str:
    return _run(["git", "-C", str(worktree_path), "diff", "main...HEAD"]).stdout

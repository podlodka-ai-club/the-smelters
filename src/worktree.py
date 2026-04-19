from __future__ import annotations

from pathlib import Path
import subprocess


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def create_worktree(repo: Path, *, task_id: int, worktrees_root: Path) -> Path:
    branch = f"task-{task_id}"
    worktree_path = worktrees_root / branch
    worktrees_root.mkdir(parents=True, exist_ok=True)
    if worktree_path.exists():
        return worktree_path

    existing = _run(["git", "-C", str(repo), "branch", "--list", branch]).stdout
    if existing.strip():
        _run(["git", "-C", str(repo), "worktree", "add", str(worktree_path), branch])
    else:
        _run(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree_path), "main"])

    return worktree_path


def remove_worktree(repo: Path, worktree_path: Path, *, branch: str | None = None) -> None:
    _run(["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree_path)])
    if branch:
        subprocess.run(
            ["git", "-C", str(repo), "branch", "-D", branch],
            capture_output=True,
            text=True,
        )


def diff_vs_main(worktree_path: Path) -> str:
    return _run(["git", "-C", str(worktree_path), "diff", "main...HEAD"]).stdout

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


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

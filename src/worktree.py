from __future__ import annotations

from pathlib import Path
import subprocess


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{details}") from exc


def _worktree_path_for_branch(repo: Path, branch: str) -> Path | None:
    output = _run(["git", "-C", str(repo), "worktree", "list", "--porcelain"]).stdout
    current_path: Path | None = None
    current_branch: str | None = None
    for line in output.splitlines():
        if not line:
            if current_path is not None and current_branch == branch:
                return current_path
            current_path = None
            current_branch = None
            continue
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ").strip())
        elif line.startswith("branch refs/heads/"):
            current_branch = line.removeprefix("branch refs/heads/").strip()

    if current_path is not None and current_branch == branch:
        return current_path
    return None


def create_worktree(repo: Path, *, task_id: int, worktrees_root: Path) -> Path:
    branch = f"task-{task_id}"
    worktree_path = worktrees_root / branch
    worktrees_root.mkdir(parents=True, exist_ok=True)

    # Repeated runs can leave missing worktrees registered in git metadata.
    _run(["git", "-C", str(repo), "worktree", "prune"])

    if worktree_path.exists():
        return worktree_path

    branch_worktree = _worktree_path_for_branch(repo, branch)
    if branch_worktree is not None and branch_worktree != worktree_path:
        _run(["git", "-C", str(repo), "worktree", "remove", "--force", str(branch_worktree)])

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

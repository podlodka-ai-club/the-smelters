from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from src.worktree import create_worktree, diff_vs_main, remove_worktree


def _write_commit(repo: Path, relpath: str, content: str, msg: str) -> None:
    (repo / relpath).write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-m", msg],
        check=True,
        capture_output=True,
        text=True,
    )


def test_create_worktree_makes_branch_and_dir(tmp_target_repo: Path, tmp_path: Path) -> None:
    _write_commit(tmp_target_repo, "a.txt", "hello\n", "add a.txt")
    worktrees_root = tmp_path / "worktrees"
    worktree_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=worktrees_root)
    assert worktree_path.exists()
    assert (worktree_path / "a.txt").read_text() == "hello\n"
    branches = subprocess.run(
        ["git", "-C", str(tmp_target_repo), "branch", "--list", "task-1"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "task-1" in branches


def test_create_worktree_idempotent_returns_existing(tmp_target_repo: Path, tmp_path: Path) -> None:
    _write_commit(tmp_target_repo, "a.txt", "hello\n", "add a.txt")
    worktrees_root = tmp_path / "worktrees"
    path_one = create_worktree(tmp_target_repo, task_id=1, worktrees_root=worktrees_root)
    path_two = create_worktree(tmp_target_repo, task_id=1, worktrees_root=worktrees_root)
    assert path_one == path_two


def test_diff_vs_main_shows_only_worktree_changes(tmp_target_repo: Path, tmp_path: Path) -> None:
    _write_commit(tmp_target_repo, "a.txt", "hello\n", "add a.txt")
    worktree_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=tmp_path / "wt")
    (worktree_path / "a.txt").write_text("hello world\n")
    subprocess.run(["git", "-C", str(worktree_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree_path), "-c", "commit.gpgsign=false", "commit", "-m", "edit"],
        check=True,
        capture_output=True,
        text=True,
    )
    diff = diff_vs_main(worktree_path)
    assert "hello world" in diff
    assert "-hello" in diff


def test_remove_worktree_cleans_up(tmp_target_repo: Path, tmp_path: Path) -> None:
    _write_commit(tmp_target_repo, "a.txt", "hello\n", "add a.txt")
    worktree_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=tmp_path / "wt")
    remove_worktree(tmp_target_repo, worktree_path, branch="task-1")
    assert not worktree_path.exists()


def test_create_worktree_prunes_stale_git_metadata(tmp_target_repo: Path, tmp_path: Path) -> None:
    _write_commit(tmp_target_repo, "a.txt", "hello\n", "add a.txt")
    worktrees_root = tmp_path / "wt"
    stale_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=worktrees_root)

    shutil.rmtree(stale_path)

    recreated_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=worktrees_root)

    assert recreated_path == stale_path
    assert recreated_path.exists()
    assert (recreated_path / "a.txt").read_text() == "hello\n"


def test_create_worktree_reclaims_existing_task_branch_from_old_path(
    tmp_target_repo: Path,
    tmp_path: Path,
) -> None:
    _write_commit(tmp_target_repo, "a.txt", "hello\n", "add a.txt")
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"

    old_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=old_root)
    new_path = create_worktree(tmp_target_repo, task_id=1, worktrees_root=new_root)

    assert old_path != new_path
    assert not old_path.exists()
    assert new_path.exists()
    assert (new_path / "a.txt").read_text() == "hello\n"

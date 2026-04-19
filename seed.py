"""Scan tasks/*.md, upsert every task into tasks.db as 'ready'."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

from src.tracker import Tracker


def _first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "<untitled>"


def _project_name(markdown: str) -> str:
    for line in markdown.splitlines():
        match = re.match(r"^\s*Project\s*:\s*(.+?)\s*$", line, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    raise AssertionError("task markdown must include a 'Project: <name>' line")


def _git_cmd(target_repo: Path, *args: str) -> list[str]:
    local_git_dir = target_repo / ".git"
    hidden_git_dir = target_repo.parent / f".{target_repo.name}_git"
    if local_git_dir.exists():
        return ["git", "-C", str(target_repo), *args]
    if hidden_git_dir.exists():
        return [
            "git",
            f"--git-dir={hidden_git_dir}",
            f"--work-tree={target_repo}",
            *args,
        ]
    raise AssertionError(f"{target_repo} is not a git repo")


def _assert_project_repo_ready(project_repo: Path) -> None:
    branch = subprocess.run(
        _git_cmd(project_repo, "rev-parse", "--abbrev-ref", "HEAD"),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == "main", f"{project_repo} must be on branch 'main', got '{branch}'"


def seed(db_path: Path, *, tasks_root: Path, projects_root: Path) -> None:
    assert tasks_root.is_dir(), f"{tasks_root} missing"
    assert projects_root.is_dir(), f"{projects_root} missing"

    tracker = Tracker(db_path)
    tracker.init_schema()
    existing = {(row.project, row.spec_path) for row in tracker.list_tasks()}

    inserted = 0
    for markdown_file in sorted(tasks_root.glob("*.md")):
        markdown = markdown_file.read_text(encoding="utf-8")
        title = _first_heading(markdown)
        project = _project_name(markdown)
        project_repo = projects_root / project
        assert project_repo.is_dir(), f"project repo missing: {project_repo}"
        _assert_project_repo_ready(project_repo)
        spec_path = f"tasks/{markdown_file.name}"
        if (project, spec_path) in existing:
            continue
        tracker.insert_task(title=title, project=project, spec_path=spec_path)
        inserted += 1
        print(f"+ task: [{project}] {title}")

    print(f"Inserted {inserted} new task(s).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="tasks.db", type=Path)
    parser.add_argument("--tasks", default="tasks", type=Path)
    parser.add_argument("--projects", default="projects", type=Path)
    args = parser.parse_args(argv)
    seed(args.db, tasks_root=args.tasks, projects_root=args.projects)
    return 0


if __name__ == "__main__":
    sys.exit(main())

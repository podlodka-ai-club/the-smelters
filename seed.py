"""Scan tasks/<project>/*.md, upsert every task into tasks.db as 'ready'."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from src.runtime_paths import project_runtime_paths
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


def _task_number_from_filename(path: Path) -> int:
    match = re.match(r"^(\d+)[-_]", path.name)
    if match:
        return int(match.group(1))
    raise AssertionError(f"task filename must start with an integer prefix: {path.name}")


def seed(db_path: Path, *, project: str, tasks_root: Path, projects_root: Path) -> None:
    assert tasks_root.is_dir(), f"{tasks_root} missing"
    assert projects_root.is_dir(), f"{projects_root} missing"
    project_tasks = tasks_root / project
    project_repo = projects_root / project
    assert project_tasks.is_dir(), f"{project_tasks} missing"
    assert project_repo.is_dir(), f"project repo missing: {project_repo}"

    tracker = Tracker(db_path)
    tracker.init_schema()
    existing = {row.task_number for row in tracker.list_tasks()}

    inserted = 0
    for markdown_file in sorted(project_tasks.glob("*.md")):
        markdown = markdown_file.read_text(encoding="utf-8")
        title = _first_heading(markdown)
        declared_project = _project_name(markdown)
        assert declared_project == project, (
            f"task markdown project mismatch: expected {project!r}, got {declared_project!r}"
        )
        task_number = _task_number_from_filename(markdown_file)
        relative_path = markdown_file.relative_to(tasks_root).as_posix()
        spec_path = f"tasks/{relative_path}"
        if task_number in existing:
            continue
        tracker.insert_task(task_number=task_number, title=title, spec_path=spec_path)
        inserted += 1
        print(f"+ task: [{project} #{task_number}] {title}")

    print(f"Inserted {inserted} new task(s).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--tasks", type=Path)
    parser.add_argument("--projects", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    runtime = project_runtime_paths(root, args.project)
    db_path = args.db.resolve() if args.db else runtime.db_path
    tasks_root = args.tasks.resolve() if args.tasks else root / "tasks"
    projects_root = args.projects.resolve() if args.projects else root / "projects"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    seed(db_path, project=args.project, tasks_root=tasks_root, projects_root=projects_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())

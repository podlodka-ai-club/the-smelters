from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProjectRuntimePaths:
    project: str
    repo_path: Path
    tasks_path: Path
    db_path: Path
    events_path: Path
    worktrees_path: Path


def project_runtime_paths(root: Path, project: str) -> ProjectRuntimePaths:
    return ProjectRuntimePaths(
        project=project,
        repo_path=root / "projects" / project,
        tasks_path=root / "tasks" / project,
        db_path=root / "database" / project / "tasks.db",
        events_path=root / "database" / project / "events.jsonl",
        worktrees_path=root / "worktrees" / project,
    )


def infer_project_from_tracker_db(db_path: Path) -> str | None:
    """Return project name from ``.../database/<Project>/tasks.db``."""
    parts = db_path.resolve().parts
    try:
        idx = parts.index("database")
    except ValueError:
        return None
    if idx + 1 < len(parts):
        return parts[idx + 1]
    return None

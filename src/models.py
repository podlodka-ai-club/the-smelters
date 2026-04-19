from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["ready", "running", "review", "needs_fixes", "closed", "failed"]


@dataclass(slots=True)
class Task:
    id: int
    title: str
    project: str
    spec_path: str
    status: Status
    attempts: int
    worktree: str | None
    branch: str | None
    review_notes: str | None


@dataclass(slots=True)
class AgentResult:
    exit_code: int
    stdout_final: str
    error: str | None = None

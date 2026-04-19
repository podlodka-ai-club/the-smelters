"""Main orchestrator loop. Pulls tasks, spawns Coder then Reviewer, loops on rejection."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

from agents.runner import run_agent
from src.events import emit_event
from src.models import Task
from src.tracker import Tracker
from src.worktree import create_worktree


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_CODER_TIMEOUT = 180
DEFAULT_REVIEWER_TIMEOUT = 90


@dataclass
class Verdict:
    approved: bool
    notes: str


def _parse_verdict(stdout_final: str) -> Verdict:
    try:
        payload = json.loads(stdout_final)
        approved = bool(payload["approved"])
        notes = str(payload.get("notes", ""))
        return Verdict(approved=approved, notes=notes)
    except (ValueError, KeyError, TypeError):
        return Verdict(approved=False, notes="Reviewer returned malformed JSON")


class Orchestrator:
    def __init__(
        self,
        *,
        tracker: Tracker,
        events_path: Path,
        projects_root: Path,
        tasks_root: Path,
        worktrees_root: Path,
        coder_role: str = "coder",
        reviewer_role: str = "reviewer",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        coder_timeout: float = DEFAULT_CODER_TIMEOUT,
        reviewer_timeout: float = DEFAULT_REVIEWER_TIMEOUT,
    ) -> None:
        self.tracker = tracker
        self.events_path = events_path
        self.projects_root = projects_root
        self.tasks_root = tasks_root
        self.worktrees_root = worktrees_root
        self.coder_role = coder_role
        self.reviewer_role = reviewer_role
        self.max_attempts = max_attempts
        self.coder_timeout = coder_timeout
        self.reviewer_timeout = reviewer_timeout

    def _project_repo(self, task: Task) -> Path:
        project_repo = self.projects_root / task.project
        if not project_repo.is_dir():
            raise AssertionError(f"project repo missing: {project_repo}")
        return project_repo

    async def _handle_task(self, task: Task) -> None:
        emit_event(
            self.events_path,
            task_id=task.id,
            actor="orchestrator",
            type="task_claimed",
            attempt=task.attempts + 1,
        )

        os.environ["TASKS_ROOT"] = str(self.tasks_root)

        if task.worktree is None:
            project_repo = self._project_repo(task)
            worktree_path = create_worktree(
                project_repo,
                task_id=task.id,
                worktrees_root=self.worktrees_root / task.project,
            )
            self.tracker.set_worktree(task.id, worktree=str(worktree_path), branch=f"task-{task.id}")
            task = self.tracker.get_task(task.id)
            emit_event(
                self.events_path,
                task_id=task.id,
                actor="orchestrator",
                type="worktree_created",
                branch=task.branch,
            )

        coder_result = await run_agent(
            role=self.coder_role,
            task=task,
            events_path=self.events_path,
            timeout=self.coder_timeout,
        )
        if coder_result.exit_code != 0:
            self._after_failure(task, f"coder_crash: {coder_result.error}")
            return

        self.tracker.set_status(task.id, "review")
        reviewer_result = await run_agent(
            role=self.reviewer_role,
            task=task,
            events_path=self.events_path,
            timeout=self.reviewer_timeout,
        )
        verdict = (
            Verdict(False, f"reviewer_crash: {reviewer_result.error}")
            if reviewer_result.exit_code != 0
            else _parse_verdict(reviewer_result.stdout_final)
        )
        emit_event(
            self.events_path,
            task_id=task.id,
            actor="reviewer",
            type="verdict",
            verdict="approved" if verdict.approved else "rejected",
            notes=verdict.notes,
        )

        if verdict.approved:
            self.tracker.set_status(task.id, "closed")
            emit_event(self.events_path, task_id=task.id, actor="orchestrator", type="task_closed")
        else:
            self._after_failure(task, verdict.notes)

    def _after_failure(self, task: Task, reason: str) -> None:
        self.tracker.increment_attempts(task.id)
        new_attempts = task.attempts + 1
        self.tracker.save_review_notes(task.id, reason)
        if new_attempts >= self.max_attempts:
            self.tracker.set_status(task.id, "failed")
            emit_event(
                self.events_path,
                task_id=task.id,
                actor="orchestrator",
                type="task_failed",
                reason=reason,
            )
        else:
            self.tracker.set_status(task.id, "ready")
            emit_event(
                self.events_path,
                task_id=task.id,
                actor="orchestrator",
                type="needs_fixes",
                notes=reason,
            )

    async def run_until_empty(self) -> None:
        while True:
            task = self.tracker.claim_next_ready_task()
            if task is None:
                return
            await self._handle_task(task)

    async def run_watching(self, *, poll_interval: float = 1.0) -> None:
        while True:
            task = self.tracker.claim_next_ready_task()
            if task is None:
                await asyncio.sleep(poll_interval)
                continue
            await self._handle_task(task)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="tasks.db", type=Path)
    parser.add_argument("--events", default="events.jsonl", type=Path)
    parser.add_argument("--tasks", default="tasks", type=Path)
    parser.add_argument("--projects", default="projects", type=Path)
    parser.add_argument("--worktrees", default="worktrees", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    args = parser.parse_args(argv)

    args.db = args.db.resolve()
    args.events = args.events.resolve()
    args.tasks = args.tasks.resolve()
    args.projects = args.projects.resolve()
    args.worktrees = args.worktrees.resolve()

    os.environ["TRACKER_DB"] = str(args.db)
    os.environ["TASKS_ROOT"] = str(args.tasks)

    tracker = Tracker(args.db)
    tracker.init_schema()
    tracker.reset_stuck_tasks()

    orchestrator = Orchestrator(
        tracker=tracker,
        events_path=args.events,
        projects_root=args.projects,
        tasks_root=args.tasks,
        worktrees_root=args.worktrees,
        max_attempts=args.max_attempts,
    )
    emit_event(args.events, task_id=None, actor="orchestrator", type="startup")
    if args.watch:
        asyncio.run(orchestrator.run_watching())
    else:
        asyncio.run(orchestrator.run_until_empty())
    return 0


if __name__ == "__main__":
    sys.exit(main())

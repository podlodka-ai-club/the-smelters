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
from src.runtime_paths import project_runtime_paths
from src.tracker import Tracker
from src.worktree import ensure_task_worktree_dir


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_CODER_TIMEOUT = 600  # 10 minutes instead of 3 minutes
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
        project: str,
        root_path: Path,
        events_path: Path,
        projects_root: Path,
        tasks_root: Path,
        worktrees_root: Path,
        coder_role: str = "coder",
        reviewer_role: str = "reviewer",
        task_filter: int | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        coder_timeout: float = DEFAULT_CODER_TIMEOUT,
        reviewer_timeout: float = DEFAULT_REVIEWER_TIMEOUT,
    ) -> None:
        self.tracker = tracker
        self.project = project
        self.root_path = root_path
        self.events_path = events_path
        self.projects_root = projects_root
        self.tasks_root = tasks_root
        self.worktrees_root = worktrees_root
        self.coder_role = coder_role
        self.reviewer_role = reviewer_role
        self.task_filter = task_filter
        self.max_attempts = max_attempts
        self.coder_timeout = coder_timeout
        self.reviewer_timeout = reviewer_timeout

    def _project_repo(self) -> Path:
        project_repo = self.projects_root / self.project
        if not project_repo.is_dir():
            raise AssertionError(f"project repo missing: {project_repo}")
        return project_repo

    def _task_filter_status(self) -> tuple[str, int] | None:
        if self.task_filter is None:
            return None
        for task in self.tracker.list_tasks():
            if task.task_number == self.task_filter:
                return task.status, task.attempts
        return None

    async def _handle_task(self, task: Task) -> None:
        print(
            f"[orchestrator] claiming task #{task.task_number} ({task.title})",
            file=sys.stderr,
            flush=True,
        )
        emit_event(
            self.events_path,
            task_id=task.task_number,
            actor="orchestrator",
            type="task_claimed",
            attempt=task.attempts + 1,
        )

        os.environ["TRACKER_DB"] = str(self.tracker.db_path)
        os.environ["TASKS_ROOT"] = str(self.tasks_root)
        os.environ["REPO_ROOT"] = str(self.root_path)
        os.environ["EVENTS_PATH"] = str(self.events_path)

        _, worktree_changed = ensure_task_worktree_dir(
            repo_root=self.root_path,
            tracker=self.tracker,
            task_id=task.id,
            db_path=self.tracker.db_path,
            project=self.project,
        )
        if worktree_changed:
            task = self.tracker.get_task(task.id)
            emit_event(
                self.events_path,
                task_id=task.task_number,
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
        print(
            f"[orchestrator] coder exit_code={coder_result.exit_code}",
            file=sys.stderr,
            flush=True,
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
        print(
            f"[orchestrator] reviewer exit_code={reviewer_result.exit_code}, verdict={'approved' if verdict.approved else 'rejected'}",
            file=sys.stderr,
            flush=True,
        )
        emit_event(
            self.events_path,
            task_id=task.task_number,
            actor="reviewer",
            type="verdict",
            verdict="approved" if verdict.approved else "rejected",
            notes=verdict.notes,
        )

        if verdict.approved:
            self.tracker.set_status(task.id, "closed")
            emit_event(
                self.events_path,
                task_id=task.task_number,
                actor="orchestrator",
                type="task_closed",
            )
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
                task_id=task.task_number,
                actor="orchestrator",
                type="task_failed",
                reason=reason,
            )
        else:
            self.tracker.set_status(task.id, "ready")
            emit_event(
                self.events_path,
                task_id=task.task_number,
                actor="orchestrator",
                type="needs_fixes",
                notes=reason,
            )

    async def run_until_empty(self) -> None:
        while True:
            task = self.tracker.claim_next_ready_task(
                task_id=self.task_filter,
            )
            if task is None:
                task_state = self._task_filter_status()
                if self.task_filter is not None and task_state is not None:
                    status, attempts = task_state
                    print(
                        "[orchestrator] no ready task matching "
                        f"--task={self.task_filter} (current status: {status}, attempts={attempts}). "
                        "Reset with: sqlite3 database/DemoApp/tasks.db "
                        "\"UPDATE tasks SET status='ready', attempts=0, review_notes=NULL "
                        f"WHERE task_number={self.task_filter}\"",
                        file=sys.stderr,
                        flush=True,
                    )
                elif self.task_filter is not None:
                    print(
                        f"[orchestrator] no task found for --task={self.task_filter}",
                        file=sys.stderr,
                        flush=True,
                    )
                return
            await self._handle_task(task)

    async def run_watching(self, *, poll_interval: float = 1.0) -> None:
        while True:
            task = self.tracker.claim_next_ready_task(
                task_id=self.task_filter,
            )
            if task is None:
                await asyncio.sleep(poll_interval)
                continue
            await self._handle_task(task)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--task", type=int, default=None)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--coder-role", default="coder")
    parser.add_argument("--reviewer-role", default="reviewer")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--coder-timeout", type=int, default=DEFAULT_CODER_TIMEOUT, help="Timeout in seconds for coder (default: 180)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    runtime = project_runtime_paths(root, args.project)
    runtime.db_path.parent.mkdir(parents=True, exist_ok=True)
    tracker = Tracker(runtime.db_path)
    tracker.init_schema()
    tracker.reset_stuck_tasks()

    orchestrator = Orchestrator(
        tracker=tracker,
        project=args.project,
        root_path=root,
        events_path=runtime.events_path,
        projects_root=root / "projects",
        tasks_root=root / "tasks",
        worktrees_root=runtime.worktrees_path,
        coder_role=args.coder_role,
        reviewer_role=args.reviewer_role,
        task_filter=args.task,
        max_attempts=args.max_attempts,
        coder_timeout=args.coder_timeout,
    )
    emit_event(runtime.events_path, task_id=None, actor="orchestrator", type="startup")
    if args.watch:
        asyncio.run(orchestrator.run_watching())
    else:
        asyncio.run(orchestrator.run_until_empty())
    return 0


if __name__ == "__main__":
    sys.exit(main())

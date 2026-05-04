"""Inspect Agno workflow run output + session state after a Smelters run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from agno.run.base import RunStatus
from agno.run.workflow import LoopExecutionCompletedEvent, LoopIterationCompletedEvent
from agno.workflow import Workflow


@dataclass(frozen=True)
class SmeltersPostRunSummary:
    """Outcome signals used for resume I/O and the whole-flow failure banner."""

    session_id: str
    pr_create_step_ran: bool
    pr_create_ok: bool
    last_checker_raw: Optional[str]
    coder_loop_total_iterations: Optional[int]
    coder_loop_max_iterations: Optional[int]
    workflow_completed: bool


def _last_checker_from_events(events: list[Any] | None) -> str | None:
    if not events:
        return None
    last: str | None = None
    for ev in events:
        if isinstance(ev, LoopIterationCompletedEvent):
            results = ev.iteration_results or []
            if not results:
                continue
            tail = results[-1]
            content = getattr(tail, "content", None)
            if isinstance(content, str) and content.strip():
                last = content
    return last


def _coder_loop_execution_stats(events: list[Any] | None) -> tuple[int | None, int | None]:
    if not events:
        return None, None
    total: int | None = None
    max_i: int | None = None
    for ev in events:
        if isinstance(ev, LoopExecutionCompletedEvent) and getattr(ev, "step_name", None) == "CoderCheckerLoop":
            total = ev.total_iterations
            max_i = ev.max_iterations
    return total, max_i


def summarize_smelters_post_run(workflow: Workflow, session_id: str) -> SmeltersPostRunSummary:
    state = workflow.get_session_state(session_id) or {}
    pr_payload = state.get("pr_create_result")
    pr_create_step_ran = "pr_create_result" in state
    pr_create_ok = isinstance(pr_payload, dict) and bool(pr_payload.get("ok"))

    run = workflow.get_last_run_output(session_id)
    events = list(run.events) if run and run.events else []
    last_checker = _last_checker_from_events(events)
    total_it, max_it = _coder_loop_execution_stats(events)

    completed = bool(run is not None and run.status == RunStatus.completed)

    return SmeltersPostRunSummary(
        session_id=session_id,
        pr_create_step_ran=pr_create_step_ran,
        pr_create_ok=pr_create_ok,
        last_checker_raw=last_checker,
        coder_loop_total_iterations=total_it,
        coder_loop_max_iterations=max_it,
        workflow_completed=completed,
    )

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.smelters_review_context import SmeltersReviewContext


@dataclass(frozen=True)
class ReviewerRequest:
    backend: str
    task_context_mode: str
    task_path: str
    task_markdown: str
    repo: str
    pr_number: int | None
    pr_url: str | None


@dataclass(frozen=True)
class ReviewerResult:
    ok: bool
    approved: bool | None
    notes: str
    raw_output: str


@dataclass(frozen=True)
class StepOutputLike:
    content: str


def build_reviewer_request(
    context: SmeltersReviewContext,
    *,
    backend: str,
    pr_number: int | None,
    pr_url: str | None,
) -> ReviewerRequest:
    return ReviewerRequest(
        backend=backend,
        task_context_mode=context.task_context_mode,
        task_path=context.task_path,
        task_markdown=context.task_markdown,
        repo=context.repo,
        pr_number=pr_number,
        pr_url=pr_url,
    )


def build_reviewer_prompt(request: ReviewerRequest) -> str:
    if request.task_context_mode == "path":
        context_block = f"Task spec path: {request.task_path}"
    else:
        context_block = (
            f"Task spec path: {request.task_path}\n"
            f"Task spec markdown:\n```md\n{request.task_markdown}\n```"
        )
    return (
        "Review this PR against the task requirements.\n"
        f"Repo: {request.repo}\n"
        f"PR: {request.pr_url or request.pr_number}\n"
        f"{context_block}\n"
        'Return last line JSON: {"approved": true|false, "notes":"..."}'
    )


def _parse_verdict(raw_output: str) -> ReviewerResult:
    """Parse final reviewer JSON line into a normalized result."""
    lines = [line.strip() for line in (raw_output or "").splitlines() if line.strip()]
    if not lines:
        return ReviewerResult(ok=False, approved=None, notes="Reviewer produced no output", raw_output=raw_output)
    last = lines[-1]
    try:
        parsed = json.loads(last)
    except json.JSONDecodeError:
        return ReviewerResult(ok=False, approved=None, notes="Reviewer did not emit valid JSON", raw_output=raw_output)
    approved = parsed.get("approved")
    notes = str(parsed.get("notes", ""))
    if not isinstance(approved, bool):
        return ReviewerResult(ok=False, approved=None, notes="Reviewer JSON missing boolean approved field", raw_output=raw_output)
    return ReviewerResult(ok=True, approved=approved, notes=notes, raw_output=raw_output)


def run_local_reviewer(
    request: ReviewerRequest,
    *,
    run_backend: Callable[[str, str], str],
) -> ReviewerResult:
    prompt = build_reviewer_prompt(request)
    raw_output = run_backend(request.backend, prompt)
    return _parse_verdict(raw_output)


def make_pr_reviewer_step(
    context: SmeltersReviewContext,
    *,
    backend: str,
    pr_number: int | None,
    pr_url: str | None,
    run_backend: Callable[[str, str], str],
):
    """Create workflow step that runs local reviewer and stores result in session state."""
    request = build_reviewer_request(
        context,
        backend=backend,
        pr_number=pr_number,
        pr_url=pr_url,
    )

    def _pr_reviewer_step(step_input: Any, session_state: Optional[dict[str, Any]] = None):
        _ = step_input
        result = run_local_reviewer(request, run_backend=run_backend)
        payload = {
            "ok": result.ok,
            "approved": result.approved,
            "notes": result.notes,
            "raw_output": result.raw_output,
        }
        if session_state is not None:
            session_state["pr_reviewer_result"] = payload.copy()
        return StepOutputLike(content=json.dumps(payload))

    _pr_reviewer_step.__name__ = "pr_reviewer_step"
    return _pr_reviewer_step

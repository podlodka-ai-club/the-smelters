from __future__ import annotations

import json

from agno_tools.pr_reviewer_step import (
    build_reviewer_prompt,
    build_reviewer_request,
    make_pr_reviewer_step,
    run_local_reviewer,
)
from src.smelters_review_context import SmeltersReviewContext


def _context(mode: str = "inline") -> SmeltersReviewContext:
    return SmeltersReviewContext(
        repo="podlodka-ai-club/the-smelters",
        base_branch="main",
        head_branch=None,
        pr_title=None,
        pr_body_file=None,
        github_token_env="GITHUB_TOKEN",
        task_context_mode=mode,
        task_path="tasks/the-smelters/005.md",
        task_markdown="# Reviewer task",
        project_scope_posix="projects/DemoApp",
    )


def test_build_reviewer_prompt_includes_inline_task_markdown() -> None:
    request = build_reviewer_request(_context("inline"), backend="claude", pr_number=10, pr_url=None)
    prompt = build_reviewer_prompt(request)
    assert "Task spec path: tasks/the-smelters/005.md" in prompt
    assert "Task spec markdown:" in prompt
    assert "# Reviewer task" in prompt


def test_build_reviewer_prompt_path_mode_skips_markdown_body() -> None:
    request = build_reviewer_request(_context("path"), backend="opencode", pr_number=None, pr_url="https://x/pr/1")
    prompt = build_reviewer_prompt(request)
    assert "Task spec path: tasks/the-smelters/005.md" in prompt
    assert "Task spec markdown:" not in prompt


def test_run_local_reviewer_parses_valid_verdict() -> None:
    request = build_reviewer_request(_context(), backend="claude", pr_number=10, pr_url=None)

    def _backend(backend: str, prompt: str) -> str:
        return 'review text\n{"approved": true, "notes": "Looks good"}\n'

    result = run_local_reviewer(request, run_backend=_backend)
    assert result.ok is True
    assert result.approved is True
    assert result.notes == "Looks good"


def test_run_local_reviewer_handles_malformed_output() -> None:
    request = build_reviewer_request(_context(), backend="claude", pr_number=10, pr_url=None)

    def _backend(backend: str, prompt: str) -> str:
        return "not-json"

    result = run_local_reviewer(request, run_backend=_backend)
    assert result.ok is False
    assert "valid JSON" in result.notes


def test_make_pr_reviewer_step_writes_session_state() -> None:
    session_state: dict[str, object] = {}
    step = make_pr_reviewer_step(
        _context(),
        backend="claude",
        pr_number=77,
        pr_url=None,
        run_backend=lambda backend, prompt: '{"approved": false, "notes": "Fix issues"}',
    )
    output = step(step_input=None, session_state=session_state)
    payload = json.loads(output.content)
    assert payload["approved"] is False
    assert session_state["pr_reviewer_result"]["notes"] == "Fix issues"


def test_make_pr_reviewer_step_passes_context_to_backend() -> None:
    seen = {"prompt": ""}

    def _backend(backend: str, prompt: str) -> str:
        seen["prompt"] = prompt
        return '{"approved": true, "notes": "ok"}'

    step = make_pr_reviewer_step(
        _context("inline"),
        backend="claude",
        pr_number=9,
        pr_url="https://github.com/podlodka-ai-club/the-smelters/pull/9",
        run_backend=_backend,
    )
    _ = step(step_input=None, session_state={})

    assert "Task spec path: tasks/the-smelters/005.md" in seen["prompt"]
    assert "Task spec markdown:" in seen["prompt"]

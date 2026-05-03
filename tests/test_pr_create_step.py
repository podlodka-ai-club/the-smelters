from __future__ import annotations

import json

from agno_tools.pr_create_step import (
    GhCommandResult,
    build_pr_create_request,
    create_or_reuse_pull_request,
    make_pr_create_step,
)
from src.smelters_review_context import SmeltersReviewContext


def _context() -> SmeltersReviewContext:
    return SmeltersReviewContext(
        repo="podlodka-ai-club/the-smelters",
        base_branch="main",
        head_branch="feature/abc",
        pr_title="My PR",
        pr_body_file=None,
        github_token_env="GITHUB_TOKEN",
        task_context_mode="inline",
        task_path="tasks/the-smelters/001.md",
        task_markdown="# task",
        project_scope_posix="projects/DemoApp",
    )


def test_build_pr_create_request_maps_context_fields() -> None:
    request = build_pr_create_request(_context())
    assert request.repo == "podlodka-ai-club/the-smelters"
    assert request.base_branch == "main"
    assert request.head_branch == "feature/abc"
    assert request.title == "My PR"


def test_make_pr_create_step_scaffold_stores_session_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "agno_tools.pr_create_step.prepare_scoped_git_for_pr",
        lambda ctx: (True, None, "feature/abc"),
    )
    monkeypatch.setattr(
        "agno_tools.pr_create_step.create_or_reuse_pull_request",
        lambda request: type(
            "FakeResult",
            (),
            {
                "ok": True,
                "pr_number": 7,
                "pr_url": "https://example/pr/7",
                "created_new": True,
                "error": None,
            },
        )(),
    )
    session_state: dict[str, object] = {}
    step = make_pr_create_step(_context())
    output = step(step_input=None, session_state=session_state)
    payload = json.loads(output.content)

    assert payload["ok"] is True
    assert "pr_create_result" in session_state


def test_create_or_reuse_pull_request_success_new_pr() -> None:
    request = build_pr_create_request(_context())

    def _runner(args: list[str]) -> GhCommandResult:
        return GhCommandResult(
            returncode=0,
            stdout="https://github.com/podlodka-ai-club/the-smelters/pull/123\n",
            stderr="",
        )

    result = create_or_reuse_pull_request(request, run_command=_runner)
    assert result.ok is True
    assert result.created_new is True
    assert result.pr_number == 123


def test_create_or_reuse_pull_request_reuses_existing() -> None:
    request = build_pr_create_request(_context())
    calls = {"count": 0}

    def _runner(args: list[str]) -> GhCommandResult:
        calls["count"] += 1
        if calls["count"] == 1:
            return GhCommandResult(
                returncode=1,
                stdout="",
                stderr="a pull request for branch already exists",
            )
        return GhCommandResult(
            returncode=0,
            stdout='[{"number":42,"url":"https://github.com/podlodka-ai-club/the-smelters/pull/42","headRefName":"feature/abc"}]',
            stderr="",
        )

    result = create_or_reuse_pull_request(request, run_command=_runner)
    assert result.ok is True
    assert result.created_new is False
    assert result.pr_number == 42


def test_create_or_reuse_pull_request_errors_when_existing_cannot_be_resolved() -> None:
    request = build_pr_create_request(_context())
    calls = {"count": 0}

    def _runner(args: list[str]) -> GhCommandResult:
        calls["count"] += 1
        if calls["count"] == 1:
            return GhCommandResult(
                returncode=1,
                stdout="",
                stderr="pull request already exists",
            )
        return GhCommandResult(
            returncode=0,
            stdout="[]",
            stderr="",
        )

    result = create_or_reuse_pull_request(request, run_command=_runner)
    assert result.ok is False
    assert "could not resolve existing PR" in (result.error or "")


def test_create_or_reuse_pull_request_returns_error_on_create_failure() -> None:
    request = build_pr_create_request(_context())

    def _runner(args: list[str]) -> GhCommandResult:
        return GhCommandResult(
            returncode=1,
            stdout="",
            stderr="authentication failed",
        )

    result = create_or_reuse_pull_request(request, run_command=_runner)
    assert result.ok is False
    assert "authentication failed" in (result.error or "")

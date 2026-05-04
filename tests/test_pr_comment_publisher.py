from __future__ import annotations

from agno_tools.pr_comment_publisher import (
    REVIEW_COMMENT_MARKER,
    GhCommandResult,
    publish_review_comment,
)


def test_publish_review_comment_creates_when_missing(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    calls: list[list[str]] = []

    def _runner(args: list[str], env: dict[str, str] | None) -> GhCommandResult:
        calls.append(args)
        if args[-1].endswith("/comments") and "-X" not in args:
            return GhCommandResult(0, "[]", "")
        return GhCommandResult(0, '{"id": 123}', "")

    result = publish_review_comment(
        repo="podlodka-ai-club/the-smelters",
        pr_number=10,
        body="Review summary",
        token_env_name="GITHUB_TOKEN",
        run_command=_runner,
    )
    assert result.ok is True
    assert result.action == "create"
    assert result.comment_id == 123
    assert any(REVIEW_COMMENT_MARKER in " ".join(cmd) for cmd in calls if "-f" in cmd)


def test_publish_review_comment_updates_existing_marker_comment(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def _runner(args: list[str], env: dict[str, str] | None) -> GhCommandResult:
        if args[-1].endswith("/comments") and "-X" not in args:
            return GhCommandResult(0, '[{"id":42,"body":"<!-- smelters-review-comment --> old"}]', "")
        return GhCommandResult(0, "{}", "")

    result = publish_review_comment(
        repo="podlodka-ai-club/the-smelters",
        pr_number=10,
        body="Updated review summary",
        token_env_name="GITHUB_TOKEN",
        run_command=_runner,
    )
    assert result.ok is True
    assert result.action == "update"
    assert result.comment_id == 42


def test_publish_review_comment_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    monkeypatch.setattr("src.github_auth.fill_github_token_from_cli", lambda _n: False)
    monkeypatch.setattr("src.github_auth.shutil.which", lambda _: None)
    result = publish_review_comment(
        repo="podlodka-ai-club/the-smelters",
        pr_number=10,
        body="x",
        token_env_name="MISSING_TOKEN",
        run_command=lambda args, env: GhCommandResult(0, "[]", ""),
    )
    assert result.ok is False
    assert "MISSING_TOKEN is not set" in (result.error or "")
    assert "not on PATH" in (result.error or "")


def test_publish_review_comment_surfaces_api_failure(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    result = publish_review_comment(
        repo="podlodka-ai-club/the-smelters",
        pr_number=10,
        body="x",
        token_env_name="GITHUB_TOKEN",
        run_command=lambda args, env: GhCommandResult(1, "", "permission denied"),
    )
    assert result.ok is False
    assert "permission denied" in (result.error or "")

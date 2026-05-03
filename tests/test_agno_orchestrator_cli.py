from __future__ import annotations

import argparse

import pytest

from src.smelters_cli_validation import validate_smelters_pr_context


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "repo": "podlodka-ai-club/the-smelters",
        "github_token_env": "GITHUB_TOKEN",
        "pr_body_file": None,
        "task_context_mode": "inline",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_validate_smelters_pr_context_accepts_valid_inputs(tmp_path, monkeypatch) -> None:
    body = tmp_path / "pr-body.md"
    body.write_text("# PR body\n", encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    validate_smelters_pr_context(_args(pr_body_file=str(body)))


def test_validate_smelters_pr_context_rejects_missing_repo(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    with pytest.raises(SystemExit, match="--repo is required"):
        validate_smelters_pr_context(_args(repo=""))


def test_validate_smelters_pr_context_rejects_bad_repo_format(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    with pytest.raises(SystemExit, match="Expected format: owner/name"):
        validate_smelters_pr_context(_args(repo="not-a-slug"))


def test_validate_smelters_pr_context_rejects_missing_token_env(monkeypatch) -> None:
    monkeypatch.delenv("MY_TOKEN", raising=False)

    with pytest.raises(SystemExit, match="MY_TOKEN is not set"):
        validate_smelters_pr_context(_args(github_token_env="MY_TOKEN"))


def test_validate_smelters_pr_context_rejects_missing_body_file(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    with pytest.raises(SystemExit, match="--pr-body-file was provided but file was not found"):
        validate_smelters_pr_context(_args(pr_body_file="missing-file.md"))


def test_validate_smelters_pr_context_accepts_path_task_context_mode(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    validate_smelters_pr_context(_args(task_context_mode="path"))


def test_validate_smelters_pr_context_rejects_bad_task_context_mode(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    with pytest.raises(SystemExit, match="unsupported --task-context-mode value"):
        validate_smelters_pr_context(_args(task_context_mode="unknown"))

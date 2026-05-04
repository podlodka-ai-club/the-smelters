from __future__ import annotations

import argparse
import os

import pytest

from src.github_auth import fill_github_token_from_cli
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


def test_validate_smelters_pr_context_rejects_missing_credential(monkeypatch) -> None:
    monkeypatch.delenv("MY_TOKEN", raising=False)
    monkeypatch.setattr("src.github_auth.fill_github_token_from_cli", lambda _n: False)

    with pytest.raises(SystemExit, match="GitHub authentication required"):
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


def test_fill_github_token_from_cli_sets_env(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "gh-token-xyz\n"

        return R()

    monkeypatch.setattr("src.github_auth.subprocess.run", fake_run)
    monkeypatch.setattr("src.github_auth.shutil.which", lambda _: "/usr/bin/gh")

    assert fill_github_token_from_cli("GITHUB_TOKEN") is True
    assert os.environ.get("GITHUB_TOKEN") == "gh-token-xyz"


def test_validate_smelters_pr_context_uses_gh_token_fallback(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def fake_run(cmd, **kwargs):
        class R:
            returncode = 0
            stdout = "from-gh\n"

        return R()

    monkeypatch.setattr("src.github_auth.subprocess.run", fake_run)
    monkeypatch.setattr("src.github_auth.shutil.which", lambda _: "/gh")

    validate_smelters_pr_context(_args())
    assert os.environ.get("GITHUB_TOKEN") == "from-gh"

from __future__ import annotations

import pytest

from src.github_auth import (
    ensure_github_token_or_exit,
    fill_github_token_from_cli,
    missing_github_token_message,
)


def test_fill_github_token_from_cli_noop_when_set(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    assert fill_github_token_from_cli("GITHUB_TOKEN") is True


def test_ensure_exits_when_no_credential(monkeypatch) -> None:
    monkeypatch.delenv("X_TOKEN", raising=False)
    monkeypatch.setattr("src.github_auth.fill_github_token_from_cli", lambda _n: False)
    with pytest.raises(SystemExit, match="GitHub authentication required"):
        ensure_github_token_or_exit("X_TOKEN")


def test_missing_message_mentions_gh_not_on_path(monkeypatch) -> None:
    monkeypatch.setattr("src.github_auth.shutil.which", lambda _: None)
    msg = missing_github_token_message("GITHUB_TOKEN")
    assert "not on PATH" in msg
    assert "GITHUB_TOKEN" in msg

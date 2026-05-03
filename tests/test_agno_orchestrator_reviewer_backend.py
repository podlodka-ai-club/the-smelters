"""Tests for smelters reviewer subprocess wiring (opencode model from YAML)."""

from __future__ import annotations

import subprocess

import pytest


def test_make_run_reviewer_backend_opencode_uses_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.smelters_reviewer_backend import make_run_reviewer_backend

    recorded: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout='{"approved": true, "notes": "ok"}', stderr="")

    monkeypatch.setattr("src.smelters_reviewer_backend.subprocess.run", fake_run)

    run = make_run_reviewer_backend(
        "opencode/nemotron-3-super-free",
        opencode_server_url="",
        timeout_secs=120.0,
    )
    out = run("opencode", "prompt text")

    assert out.strip().startswith("{")
    cmd = recorded["cmd"]
    assert isinstance(cmd, list)
    assert cmd[:4] == ["opencode", "run", "--model", "opencode/nemotron-3-super-free"]
    assert cmd[-1] == "prompt text"


def test_make_run_reviewer_backend_opencode_attaches_server(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.smelters_reviewer_backend import make_run_reviewer_backend

    recorded: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr("src.smelters_reviewer_backend.subprocess.run", fake_run)

    run = make_run_reviewer_backend(
        "opencode/nemotron-3-super-free",
        opencode_server_url="http://127.0.0.1:4096",
    )
    run("opencode", "x")

    cmd = recorded["cmd"]
    assert "--attach" in cmd
    attach_idx = cmd.index("--attach")
    assert cmd[attach_idx + 1] == "http://127.0.0.1:4096"

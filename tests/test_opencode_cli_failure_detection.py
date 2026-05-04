from __future__ import annotations

import json
from pathlib import Path

from agno.workflow.types import StepInput

from agno_tools.opencode_checker_step import make_opencode_checker_step
from agno_tools.opencode_subprocess import describe_opencode_cli_failure


def test_describe_opencode_cli_failure_prefers_model_not_found_line() -> None:
    text = """ProviderModelNotFoundError: x
Error: Model not found: opencode/ling-2.6-flash-free.
"""
    msg = describe_opencode_cli_failure(text)
    assert msg is not None
    assert "Model not found" in msg


def test_describe_opencode_cli_failure_provider_only() -> None:
    text = "ProviderModelNotFoundError: ProviderModelNotFoundError\ndata: {}\n"
    msg = describe_opencode_cli_failure(text)
    assert msg is not None
    assert "ProviderModelNotFoundError" in msg


def test_describe_opencode_cli_failure_none_for_clean_output() -> None:
    assert describe_opencode_cli_failure('{"status":"passed"}') is None
    assert describe_opencode_cli_failure("") is None


def test_opencode_checker_maps_exit_zero_model_error_to_infra_json(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    bad = (
        "ProviderModelNotFoundError\n"
        "Error: Model not found: opencode/missing-model.\n"
    )

    def fake_run(*_a, **_kw):
        return 0, bad

    monkeypatch.setattr("agno_tools.opencode_checker_step.run_opencode_command", fake_run)
    step = make_opencode_checker_step(str(root), model_id="opencode/missing-model", timeout_secs=5.0)
    out = step(StepInput(), None)
    data = json.loads(out.content)
    assert data["status"] == "error"
    assert data.get("scope") == "checker"
    assert "Model not found" in (data.get("detail") or "")

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from agno.workflow.types import StepInput

from agno_tools.opencode_checker_step import make_opencode_checker_step


def test_opencode_checker_exit_zero_without_contract_json(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()

    def fake_run(*_a, **_kw):
        r = MagicMock()
        r.returncode = 0
        r.stdout = "Some prose from the model.\nStill no JSON line.\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(subprocess, "run", fake_run)
    step = make_opencode_checker_step(str(root), model_id="test-model", timeout_secs=5.0)
    out = step(StepInput(), None)
    data = json.loads(out.content)
    assert data["status"] == "failed"
    assert "subprocess exit code 0" in (data.get("build_errors") or "")


def test_opencode_checker_exit_zero_with_contract_line(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    line = '{"status": "passed", "failed_tests": [], "build_errors": ""}'

    def fake_run(*_a, **_kw):
        r = MagicMock()
        r.returncode = 0
        r.stdout = f"noise\n{line}\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(subprocess, "run", fake_run)
    step = make_opencode_checker_step(str(root), model_id="test-model", timeout_secs=5.0)
    out = step(StepInput(), None)
    data = json.loads(out.content)
    assert data["status"] == "passed"

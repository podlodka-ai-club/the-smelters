"""Smelters checker step via `opencode run` (model from agent_config.yml ``opencode_checker_model``)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from agno.workflow.types import StepInput, StepOutput

from agno_agents.code_checker import CODE_CHECKER_SYSTEM_PROMPT
from agno_tools.claude_code_step import _CHECKER_USER_PROMPT


def make_opencode_checker_step(
    project_path: str,
    *,
    model_id: str,
    opencode_server_url: str = "",
    timeout_secs: float = 7200.0,
) -> Callable[[StepInput, Optional[Dict[str, Any]]], StepOutput]:
    """Checker step: same contract as Agno CodeChecker — runs RUN_TESTS.sh logic via opencode."""

    project = str(Path(project_path).resolve())
    full_prompt = f"{CODE_CHECKER_SYSTEM_PROMPT}\n\n{_CHECKER_USER_PROMPT}"

    def _opencode_checker_step(
        step_input: StepInput,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        _ = step_input
        cmd: list[str] = ["opencode", "run", "--model", model_id]
        if opencode_server_url.strip():
            cmd.extend(["--attach", opencode_server_url.strip()])
        cmd.append(full_prompt)

        sys.stdout.write(f"\n  ╭─ [opencode checker] model={model_id} (timeout {timeout_secs}s)\n")
        sys.stdout.flush()
        try:
            result = subprocess.run(
                cmd,
                cwd=project,
                text=True,
                capture_output=True,
                timeout=timeout_secs,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return StepOutput(
                content=json.dumps(
                    {
                        "status": "failed",
                        "failed_tests": [],
                        "build_errors": f"opencode checker timed out after {timeout_secs}s",
                    }
                )
            )

        text_out = (result.stdout or "") + (result.stderr or "")
        sys.stdout.write(f"  ╰─ [opencode checker] exit {result.returncode}\n\n")
        sys.stdout.flush()

        if result.returncode != 0:
            tail = text_out[-800:] if text_out else ""
            return StepOutput(
                content=json.dumps(
                    {
                        "status": "failed",
                        "failed_tests": [],
                        "build_errors": tail[:2000],
                    }
                )
            )
        return StepOutput(content=text_out or result.stdout or "")

    _opencode_checker_step.__name__ = "opencode_checker_step"
    return _opencode_checker_step

"""Smelters checker step via `opencode run` (model from agent_config.yml ``opencode_checker_model``)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from agno.workflow.types import StepInput, StepOutput

from agno_agents.code_checker import CODE_CHECKER_SYSTEM_PROMPT
from agno_tools.claude_code_step import _CHECKER_USER_PROMPT
from agno_tools.opencode_subprocess import describe_opencode_cli_failure, run_opencode_command
from shared.checker_utils import emit_checker_infrastructure_json, normalize_checker_stdout_to_json_content


def make_opencode_checker_step(
    project_path: str,
    *,
    model_id: str,
    opencode_server_url: str = "",
    timeout_secs: float = 7200.0,
    stream_output: bool = False,
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
            returncode, text_out = run_opencode_command(
                cmd,
                project,
                timeout_secs,
                stream=stream_output,
            )
        except subprocess.TimeoutExpired:
            return StepOutput(
                content=emit_checker_infrastructure_json(
                    f"OpenCode checker timed out after {timeout_secs}s",
                    "The opencode subprocess did not finish before the configured timeout.",
                )
            )

        sys.stdout.write(f"  ╰─ [opencode checker] exit {returncode}\n\n")
        sys.stdout.flush()

        if returncode != 0:
            tail = text_out[-800:] if text_out else ""
            return StepOutput(
                content=emit_checker_infrastructure_json(
                    f"OpenCode checker exited with code {returncode}",
                    tail[:2000],
                )
            )
        cli_fail = describe_opencode_cli_failure(text_out)
        if cli_fail:
            return StepOutput(
                content=emit_checker_infrastructure_json(
                    "OpenCode checker CLI or provider error",
                    cli_fail,
                )
            )
        normalized = normalize_checker_stdout_to_json_content(text_out or "")
        return StepOutput(content=normalized)

    _opencode_checker_step.__name__ = "opencode_checker_step"
    return _opencode_checker_step

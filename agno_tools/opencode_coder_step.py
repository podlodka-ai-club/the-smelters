"""Smelters coder step via `opencode run` (separate model from reviewer in agent_config.yml)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from agno.workflow.types import StepInput, StepOutput

from agno_agents.android_coder import ANDROID_CODER_SYSTEM_PROMPT
from agno_tools.claude_code_step import _build_user_prompt_for_coder


def make_opencode_coder_step(
    project_path: str,
    task_content: str,
    *,
    model_id: str,
    opencode_server_url: str = "",
    timeout_secs: float = 7200.0,
) -> Callable[[StepInput, Optional[Dict[str, Any]]], StepOutput]:
    """Coder step: same contract as Claude-code coder — uses opencode CLI with ``model_id``."""

    project = str(Path(project_path).resolve())

    def _opencode_coder_step(
        step_input: StepInput,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        feedback = step_input.previous_step_content or ""
        user_prompt = _build_user_prompt_for_coder(task_content, feedback)
        full_prompt = f"{ANDROID_CODER_SYSTEM_PROMPT}\n\n{user_prompt}"

        cmd: list[str] = ["opencode", "run", "--model", model_id]
        if opencode_server_url.strip():
            cmd.extend(["--attach", opencode_server_url.strip()])
        cmd.append(full_prompt)

        sys.stdout.write(f"\n  ╭─ [opencode coder] model={model_id} (timeout {timeout_secs}s)\n")
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
                content=(
                    f'{{"ok": false, "error": "opencode coder timed out after {timeout_secs}s"}}'
                )
            )

        text_out = (result.stdout or "") + (result.stderr or "")
        sys.stdout.write(f"  ╰─ [opencode coder] exit {result.returncode}\n\n")
        sys.stdout.flush()

        if result.returncode != 0:
            tail = text_out[-800:] if text_out else ""
            return StepOutput(
                content=(
                    f'{{"ok": false, "error": "opencode exit {result.returncode}", '
                    f'"stderr_tail": {tail!r}}}'
                )
            )
        return StepOutput(content=text_out or result.stdout or "")

    _opencode_coder_step.__name__ = "opencode_coder_step"
    return _opencode_coder_step

"""Smelters local reviewer subprocess wiring (opencode vs claude CLI)."""

from __future__ import annotations

import subprocess
from typing import Callable, List

from agno_tools.opencode_subprocess import run_opencode_command


def make_run_reviewer_backend(
    opencode_reviewer_model: str,
    *,
    opencode_server_url: str = "",
    timeout_secs: float = 300.0,
    stream_output: bool = False,
) -> Callable[[str, str], str]:
    """Build reviewer runner; ``opencode`` backend uses ``opencode run`` with ``opencode_reviewer_model``."""

    def _run_reviewer_backend(backend: str, prompt: str) -> str:
        if backend == "claude":
            result = subprocess.run(
                ["claude", "-p", prompt],
                text=True,
                capture_output=True,
                check=False,
            )
            return result.stdout
        if backend == "opencode":
            cmd: List[str] = ["opencode", "run", "--model", opencode_reviewer_model]
            if opencode_server_url.strip():
                cmd.extend(["--attach", opencode_server_url.strip()])
            cmd.append(prompt)
            try:
                _rc, out = run_opencode_command(
                    cmd,
                    None,
                    timeout_secs,
                    stream=stream_output,
                )
            except subprocess.TimeoutExpired:
                return '{"approved": false, "notes": "opencode reviewer subprocess timed out"}'
            return out or ""
        return '{"approved": false, "notes": "Unsupported reviewer backend"}'

    return _run_reviewer_backend

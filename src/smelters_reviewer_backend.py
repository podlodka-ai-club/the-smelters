"""Smelters local reviewer subprocess wiring (opencode vs claude CLI)."""

from __future__ import annotations

import subprocess
from typing import Callable, List


def make_run_reviewer_backend(
    opencode_reviewer_model: str,
    *,
    opencode_server_url: str = "",
    timeout_secs: float = 300.0,
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
                result = subprocess.run(
                    cmd,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=timeout_secs,
                )
            except subprocess.TimeoutExpired:
                return '{"approved": false, "notes": "opencode reviewer subprocess timed out"}'
            return result.stdout
        return '{"approved": false, "notes": "Unsupported reviewer backend"}'

    return _run_reviewer_backend

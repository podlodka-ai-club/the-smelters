"""A bash tool that takes a single command STRING and runs it via `bash -c`.

Replaces agno.tools.shell.ShellTools for our agents. ShellTools expects
List[str] argv which Claude does not produce (Claude's mental model is the
Anthropic Bash tool — single command string interpreted by a shell).

Includes a deny-list mirroring the smelters reference: rm -rf /, git push,
git commit, git reset, git rebase, curl, wget, sudo, pip install, uv pip
install. Hard wall-clock timeout per command (default 300s).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional

from agno.tools import Toolkit


_DENY_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\brm\s+-rf\s+/(?:\s|$)"),
    re.compile(r"\bgit\s+(push|commit|merge|reset|rebase|tag\s+-d)\b"),
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\buv\s+pip\s+install\b"),
    re.compile(r"\bnpm\s+(install|i)\b"),
]


class BashTool(Toolkit):
    """Toolkit exposing a single function `bash(command, tail=100, timeout=300)`."""

    def __init__(self, base_dir: Optional[Path | str] = None, default_timeout: int = 300):
        super().__init__(name="bash_tool", tools=[self.bash])
        self.base_dir = Path(base_dir).resolve() if base_dir else None
        self.default_timeout = default_timeout

    def bash(self, command: str, tail: int = 100, timeout: int = 0) -> str:
        """Run a shell command via `bash -c <command>`.

        Args:
            command: the full command line as one string (e.g. "ls -R" or
                     "./gradlew :app:assembleDebug --quiet"). Pipes, &&, redirects
                     are supported because we run under a real shell.
            tail: keep at most this many trailing lines of combined stdout/stderr
                  (default 100). Pass 0 to keep the full output.
            timeout: wall-clock seconds (default 300, 0 means use the toolkit default).

        Returns:
            Combined stdout+stderr (trimmed to `tail` lines), prefixed with the
            exit code on the very first line: "EXIT_CODE: <n>\\n<output>".

        Forbidden commands (matched via regex, case-sensitive on flags) include:
            rm -rf /, git push/commit/reset/rebase, curl, wget, sudo, pip install,
            uv pip install, npm install. They return an error without execution.
        """
        if not isinstance(command, str) or not command.strip():
            return "EXIT_CODE: 1\nError: empty command"

        for pat in _DENY_PATTERNS:
            if pat.search(command):
                return f"EXIT_CODE: 126\nError: denied by policy (matched /{pat.pattern}/) — refusing to run: {command}"

        effective_timeout = timeout if timeout > 0 else self.default_timeout

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                cwd=str(self.base_dir) if self.base_dir else None,
                timeout=effective_timeout,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if tail and tail > 0:
                lines = output.splitlines()
                if len(lines) > tail:
                    output = "[... output truncated, last {} lines ...]\n".format(tail) + "\n".join(lines[-tail:])
            return f"EXIT_CODE: {result.returncode}\n{output}"
        except subprocess.TimeoutExpired:
            return f"EXIT_CODE: 124\nError: command exceeded {effective_timeout}s timeout: {command}"
        except FileNotFoundError as exc:
            return f"EXIT_CODE: 127\nError: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"EXIT_CODE: 1\nError: {type(exc).__name__}: {exc}"

"""Shared helpers for the Claude-SDK-based agents in `agents/`.

Centralizes:
- agent_config.yml loading
- Claude SDK message text extraction
- Streaming prompt wrapper
- Bash deny-list permission callback factory
- opencode/Gemini subprocess invocation
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from claude_agent_sdk.types import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "implementation": "claude",
    "agent_timeout": 7200,
}

DEFAULT_GEMINI_MODEL = "google/gemini-2.5-flash"


def load_config(env_prefix: str = "") -> dict[str, Any]:
    """Load `agent_config.yml` from REPO_ROOT or cwd; fall back to safe defaults.

    env_prefix lets orchestrator override per-role settings via env vars:
      CODER_IMPLEMENTATION / CODER_MODEL for the coder agent
      CHECKER_IMPLEMENTATION / CHECKER_MODEL for the reviewer agent
    """
    config_path = Path(os.environ.get("REPO_ROOT", Path.cwd())) / "agent_config.yml"
    if not config_path.exists():
        config_path = Path("agent_config.yml")
    config: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = dict(DEFAULT_CONFIG)

    if env_prefix:
        impl = os.environ.get(f"{env_prefix}IMPLEMENTATION")
        model = os.environ.get(f"{env_prefix}MODEL")
        if impl:
            config["implementation"] = impl
        if model:
            config["gemini_model"] = model

    return config


def apply_anthropic_key(config: dict[str, Any]) -> None:
    key = config.get("anthropic_api_key", "")
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key


def extract_text(message: object) -> str:
    """Extract text from a Claude SDK message (handles both `result` and `text` shapes)."""
    result = getattr(message, "result", None)
    if isinstance(result, str):
        return result
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    return ""


async def streaming_prompt(prompt: str) -> AsyncIterator[dict[str, object]]:
    """Wrap a string as a Claude SDK streaming user message."""
    yield {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
        "session_id": "default",
    }


def make_bash_deny_check(
    deny_patterns: list[re.Pattern[str]],
) -> Callable[..., Any]:
    """Build a Claude SDK can_use_tool callback that denies bash commands matching patterns."""

    async def _can_use_tool(
        tool_name: str,
        tool_input: dict[str, Any],
        _context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        if tool_name != "Bash":
            return PermissionResultAllow()
        command = str(tool_input.get("command", ""))
        for pattern in deny_patterns:
            if pattern.search(command):
                return PermissionResultDeny(
                    message=f"denied by policy: matches {pattern.pattern}"
                )
        return PermissionResultAllow()

    return _can_use_tool


@dataclass
class GeminiResult:
    """Result of running an opencode/Gemini subprocess. Caller formats the final JSON."""
    stdout: str
    returncode: int
    timed_out: bool
    timeout_secs: float
    error: str | None  # exception message if subprocess setup failed


async def run_gemini_subprocess(full_prompt: str, config: dict[str, Any]) -> GeminiResult:
    """Run `opencode run --model <model>` with the given prompt under a timeout.

    Returns a GeminiResult; never prints final agent JSON itself — callers do that.
    """
    gemini_api_key = config.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = gemini_api_key
    agent_timeout = float(config.get("agent_timeout", DEFAULT_CONFIG["agent_timeout"]))
    gemini_model = config.get("gemini_model", DEFAULT_GEMINI_MODEL)
    server_url = config.get("opencode_server_url", "")

    cmd = ["opencode", "run", "--model", gemini_model]
    if server_url:
        cmd += ["--attach", server_url]
    cmd.append(full_prompt)

    print(f"INFO: Running Gemini via opencode: {gemini_model}", file=sys.stderr)
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path.cwd(),
        )
        try:
            stdout_bytes, _ = await asyncio.wait_for(
                process.communicate(), timeout=agent_timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return GeminiResult(
                stdout="", returncode=1, timed_out=True,
                timeout_secs=agent_timeout, error=None,
            )
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            print(
                f"ERROR: opencode exit {process.returncode}: {stdout[-500:]}",
                file=sys.stderr,
            )
        return GeminiResult(
            stdout=stdout, returncode=process.returncode or 0,
            timed_out=False, timeout_secs=agent_timeout, error=None,
        )
    except Exception as e:
        return GeminiResult(
            stdout="", returncode=1, timed_out=False,
            timeout_secs=agent_timeout, error=str(e),
        )


def last_nonempty_line(text: str) -> str | None:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1].strip() if lines else None

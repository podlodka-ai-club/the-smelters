"""Coder agent. Invoked as `python -m agents.coder <task_id>` from the worktree cwd."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import yaml

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from src.project_profile import detect_project_profile
from src.tracker import Tracker


def _get_config() -> dict[str, Any]:
    config_path = Path(os.environ.get("REPO_ROOT", Path.cwd())) / "agent_config.yml"
    if not config_path.exists():
        config_path = Path("agent_config.yml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {"implementation": "claude", "agent_timeout": 7200}


CODER_SYSTEM_PROMPT = """
You are Coder, a focused software engineer working on ONE task at a time.

Rules:
- Read the spec file first (path is in the user prompt).
- Read the failing test or task instructions to understand the expected behavior.
- Make the minimum change needed to make the test pass.
- Do NOT modify unrelated files. Do NOT "clean up" other code.
- Do NOT modify tests unless the spec explicitly asks for it.
- Follow the verification guidance in the user prompt.
- When all tests pass, stop and summarise what you changed in 1-2 sentences.

If a previous review flagged issues, address them literally. Do not expand scope.
"""

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
BASH_DENY = [
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\buv\s+pip\s+install\b"),
]


async def _can_use_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    _context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    if tool_name != "Bash":
        return PermissionResultAllow()

    command = str(tool_input.get("command", ""))
    for pattern in BASH_DENY:
        if pattern.search(command):
            return PermissionResultDeny(message=f"denied by policy: matches {pattern.pattern}")
    return PermissionResultAllow()


def _load_task(task_id: int) -> tuple[int, str, str, str | None, str]:
    db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
    tracker = Tracker(db_path)
    row = tracker.get_task(task_id)
    repo_root = Path(os.environ.get("REPO_ROOT", Path.cwd()))
    spec_body = (repo_root / row.spec_path).read_text(encoding="utf-8")
    return row.task_number, row.title, row.spec_path, row.review_notes, spec_body


def _build_user_prompt(task_id: int) -> str:
    task_number, title, spec_path, notes, spec_body = _load_task(task_id)
    profile = detect_project_profile(Path.cwd())
    prior_notes = f"\n\nPrevious review said:\n{notes}\n" if notes else ""
    return (
        f"Task number: {task_number}\n"
        f"Title: {title}\n"
        f"Project type: {profile.label}\n"
        f"Spec path: {spec_path}{prior_notes}\n"
        "Task spec markdown:\n"
        f"```md\n{spec_body}\n```\n"
        f"Verification guidance: {profile.coder_verification}\n"
        f"Preferred default command: `{profile.default_test_command}`\n"
        "Run verification when you think you're done. If tests fail, iterate.\n"
        'When done, print ONE final line that is a JSON object: {"ok": true, "summary": "<...>"}\n'
    )


def _extract_text(message: object) -> str:
    result = getattr(message, "result", None)
    if isinstance(result, str):
        return result
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    return ""


async def _streaming_prompt(prompt: str) -> AsyncIterator[dict[str, object]]:
    yield {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
        "session_id": "default",
    }


async def _run_gemini(task_id: int, config: dict[str, Any]) -> int:
    gemini_api_key = config.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = gemini_api_key
    agent_timeout = config.get("agent_timeout", 7200)
    gemini_model = config.get("gemini_model", "google/gemini-2.5-flash")
    server_url = config.get("opencode_server_url", "")
    full_prompt = f"{CODER_SYSTEM_PROMPT}\n\n{_build_user_prompt(task_id)}"
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
            stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=agent_timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            print(json.dumps({"ok": False, "error": f"Agent timed out after {agent_timeout}s"}))
            return 1
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            print(f"ERROR: opencode exit {process.returncode}: {stdout[-500:]}", file=sys.stderr)
        lines = [line for line in stdout.splitlines() if line.strip()]
        if lines:
            candidate = lines[-1].strip()
            if candidate.startswith("{") and '"ok"' in candidate:
                print(candidate)
                return process.returncode or 0
        print(json.dumps({"ok": True, "summary": stdout[-200:] if stdout else "done"}))
        return process.returncode or 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1


async def amain(task_id: int) -> int:
    config = _get_config()
    if config.get("implementation", "claude").lower() == "gemini":
        return await _run_gemini(task_id, config)

    anthropic_api_key = config.get("anthropic_api_key", "")
    if anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key

    options = ClaudeAgentOptions(
        system_prompt=CODER_SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="acceptEdits",
        max_turns=20,
        can_use_tool=_can_use_tool,
        cwd=Path.cwd(),
    )
    last_text = ""
    async for message in query(prompt=_streaming_prompt(_build_user_prompt(task_id)), options=options):
        extracted = _extract_text(message)
        if extracted:
            last_text = extracted

    lines = [line for line in last_text.splitlines() if line.strip()]
    if lines:
        candidate = lines[-1].strip()
        if candidate.startswith("{") and '"ok"' in candidate:
            print(candidate)
            return 0

    print(json.dumps({"ok": True, "summary": last_text[:200] or "done"}))
    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    return asyncio.run(amain(task_id))


if __name__ == "__main__":
    sys.exit(main())

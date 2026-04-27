"""Coder agent. Invoked as `python -m agents.coder <task_id>` from the worktree cwd."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from shared.agent_base import (
    apply_anthropic_key,
    extract_text,
    last_nonempty_line,
    load_config,
    make_bash_deny_check,
    run_gemini_subprocess,
    streaming_prompt,
)
from src.project_profile import detect_project_profile
from src.tracker import Tracker


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

# Legacy aliases — kept so existing tests can monkeypatch by these names.
_get_config = load_config
_extract_text = extract_text
_streaming_prompt = streaming_prompt
_can_use_tool = make_bash_deny_check(BASH_DENY)


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


async def _run_gemini(task_id: int, config: dict) -> int:
    full_prompt = f"{CODER_SYSTEM_PROMPT}\n\n{_build_user_prompt(task_id)}"
    result = await run_gemini_subprocess(full_prompt, config)
    if result.timed_out:
        print(json.dumps({"ok": False, "error": f"Agent timed out after {result.timeout_secs}s"}))
        return 1
    if result.error is not None:
        print(json.dumps({"ok": False, "error": result.error}))
        return 1
    candidate = last_nonempty_line(result.stdout)
    if candidate and candidate.startswith("{") and '"ok"' in candidate:
        print(candidate)
        return result.returncode
    print(json.dumps({"ok": True, "summary": result.stdout[-200:] if result.stdout else "done"}))
    return result.returncode


async def amain(task_id: int) -> int:
    config = _get_config()
    if config.get("implementation", "claude").lower() == "gemini":
        return await _run_gemini(task_id, config)

    apply_anthropic_key(config)

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

    candidate = last_nonempty_line(last_text)
    if candidate and candidate.startswith("{") and '"ok"' in candidate:
        print(candidate)
        return 0

    print(json.dumps({"ok": True, "summary": last_text[:200] or "done"}))
    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    return asyncio.run(amain(task_id))


if __name__ == "__main__":
    sys.exit(main())

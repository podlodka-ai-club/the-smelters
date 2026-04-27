"""Reviewer agent. Read-only tools. Emits a single JSON verdict on the last line."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from shared.agent_base import (
    apply_anthropic_key,
    extract_text,
    last_nonempty_line,
    load_config,
    run_gemini_subprocess,
)
from src.project_profile import detect_project_profile
from src.tracker import Tracker


REVIEWER_SYSTEM_PROMPT = """
You are Reviewer. You do NOT write code. You verify that the Coder's change is correct and minimal.

Your tools:
- Bash: run the repo's standard verification command, inspect `git diff main...HEAD`, `git diff`, and `git status --short`
- Read / Grep / Glob: inspect files and diff

Checklist:
1. Run the verification command from the user prompt. If it fails -> verdict = rejected, notes = which checks failed.
2. Inspect both committed and uncommitted changes. Reject if you see:
   - Unrelated files changed
   - Tests modified (unless the spec allowed it)
   - Obvious hacks: hardcoded answers, try/except that swallows the original bug
   - Added imports or dependencies not needed for this fix
3. Do NOT require the change to be committed if the working tree already contains the correct minimal fix.
4. If everything looks clean -> verdict = approved.

Output ONLY on the last line, as strict JSON:
{"approved": true|false, "notes": "<one sentence>"}

Nothing else on that line.
"""

ALLOWED_TOOLS = ["Read", "Bash", "Glob", "Grep"]

# Legacy aliases — kept so existing tests can monkeypatch by these names.
_get_config = load_config
_extract_text = extract_text


def _load_task(task_id: int) -> tuple[int, str, str, str]:
    db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
    tracker = Tracker(db_path)
    row = tracker.get_task(task_id)
    repo_root = Path(os.environ.get("REPO_ROOT", Path.cwd()))
    spec_body = (repo_root / row.spec_path).read_text(encoding="utf-8")
    return row.task_number, row.title, row.spec_path, spec_body


def _build_user_prompt(task_id: int) -> str:
    task_number, title, spec_path, spec_body = _load_task(task_id)
    profile = detect_project_profile(Path.cwd())
    return (
        f"Review task #{task_number}: {title}\n"
        f"Project type: {profile.label}\n"
        f"Spec: {spec_path}\n"
        "Task spec markdown:\n"
        f"```md\n{spec_body}\n```\n"
        f"Verification guidance: {profile.reviewer_verification}\n"
        f"1. Start with `{profile.default_test_command}` and confirm the required checks pass.\n"
        "2. Read both `git diff main...HEAD` and `git diff`, plus `git status --short`, and check the change is minimal and targeted.\n"
        "3. Accept either a committed fix or a correct uncommitted working-tree fix.\n"
        '4. Output ONLY: {"approved": true|false, "notes": "..."} on the last line.\n'
    )


def _format_verdict(approved: bool, notes: str) -> str:
    return json.dumps({"approved": approved, "notes": notes})


def _parse_verdict_line(candidate: str) -> str | None:
    try:
        parsed = json.loads(candidate)
        return _format_verdict(bool(parsed["approved"]), str(parsed.get("notes", "")))
    except (ValueError, KeyError, TypeError):
        return None


async def _run_gemini(task_id: int, config: dict) -> int:
    full_prompt = f"{REVIEWER_SYSTEM_PROMPT}\n\n{_build_user_prompt(task_id)}"
    result = await run_gemini_subprocess(full_prompt, config)
    if result.timed_out:
        print(_format_verdict(False, f"Reviewer timed out after {result.timeout_secs}s"))
        return 1
    if result.error is not None:
        print(_format_verdict(False, result.error))
        return 1
    candidate = last_nonempty_line(result.stdout)
    if candidate is not None:
        formatted = _parse_verdict_line(candidate)
        if formatted is not None:
            print(formatted)
            return result.returncode
    print(_format_verdict(False, "Reviewer did not emit valid JSON"))
    return 1


async def amain(task_id: int) -> int:
    config = _get_config()
    if config.get("implementation", "claude").lower() == "gemini":
        return await _run_gemini(task_id, config)

    apply_anthropic_key(config)

    options = ClaudeAgentOptions(
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="dontAsk",
        max_turns=10,
        cwd=Path.cwd(),
    )
    last_text = ""
    async for message in query(prompt=_build_user_prompt(task_id), options=options):
        extracted = _extract_text(message)
        if extracted:
            last_text = extracted

    candidate = last_nonempty_line(last_text)
    if candidate is not None:
        formatted = _parse_verdict_line(candidate)
        if formatted is not None:
            print(formatted)
            return 0

    print(_format_verdict(False, "Reviewer did not emit valid JSON"))
    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    return asyncio.run(amain(task_id))


if __name__ == "__main__":
    sys.exit(main())

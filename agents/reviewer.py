"""Reviewer agent. Read-only tools. Emits a single JSON verdict on the last line."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

from claude_agent_sdk import ClaudeAgentOptions, query

from src.project_profile import detect_project_profile
from src.tracker import Tracker


REVIEWER_SYSTEM_PROMPT = """
You are Reviewer. You do NOT write code. You verify that the Coder's change is correct and minimal.

Your tools:
- Bash: run the repo's standard verification command, `git diff main...HEAD`, `git log --oneline main..HEAD`
- Read / Grep / Glob: inspect files and diff

Checklist:
1. Run the verification command from the user prompt. If it fails -> verdict = rejected, notes = which checks failed.
2. Inspect the diff. Reject if you see:
   - Unrelated files changed
   - Tests modified (unless the spec allowed it)
   - Obvious hacks: hardcoded answers, try/except that swallows the original bug
   - Added imports or dependencies not needed for this fix
3. If everything looks clean -> verdict = approved.

Output ONLY on the last line, as strict JSON:
{"approved": true|false, "notes": "<one sentence>"}

Nothing else on that line.
"""

ALLOWED_TOOLS = ["Read", "Bash", "Glob", "Grep"]


def _load_task(task_id: int) -> tuple[str, str, str]:
    db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
    tracker = Tracker(db_path)
    row = tracker.get_task(task_id)
    tasks_root = Path(os.environ.get("TASKS_ROOT", db_path.parent / "tasks"))
    spec_body = (tasks_root.parent / row.spec_path).read_text(encoding="utf-8")
    return row.title, row.spec_path, spec_body


def _build_user_prompt(task_id: int) -> str:
    title, spec_path, spec_body = _load_task(task_id)
    profile = detect_project_profile(Path.cwd())
    return (
        f"Review task {task_id}: {title}\n"
        f"Project type: {profile.label}\n"
        f"Spec: {spec_path}\n"
        "Task spec markdown:\n"
        f"```md\n{spec_body}\n```\n"
        f"Verification guidance: {profile.reviewer_verification}\n"
        f"1. Start with `{profile.default_test_command}` and confirm the required checks pass.\n"
        "2. Read `git diff main...HEAD` and check the diff is minimal and targeted.\n"
        '3. Output ONLY: {"approved": true|false, "notes": "..."} on the last line.\n'
    )


def _extract_text(message: object) -> str:
    result = getattr(message, "result", None)
    if isinstance(result, str):
        return result
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    return ""


async def amain(task_id: int) -> int:
    options = ClaudeAgentOptions(
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="default",
        max_turns=10,
        cwd=Path.cwd(),
    )
    last_text = ""
    async for message in query(prompt=_build_user_prompt(task_id), options=options):
        extracted = _extract_text(message)
        if extracted:
            last_text = extracted

    lines = [line for line in last_text.splitlines() if line.strip()]
    if lines:
        candidate = lines[-1].strip()
        try:
            parsed = json.loads(candidate)
            print(
                json.dumps(
                    {
                        "approved": bool(parsed["approved"]),
                        "notes": str(parsed.get("notes", "")),
                    }
                )
            )
            return 0
        except (ValueError, KeyError, TypeError):
            pass

    print(json.dumps({"approved": False, "notes": "Reviewer did not emit valid JSON"}))
    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    return asyncio.run(amain(task_id))


if __name__ == "__main__":
    sys.exit(main())

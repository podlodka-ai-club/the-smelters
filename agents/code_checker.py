"""Code checker agent. Runs RUN_TESTS.sh in the worktree, parses logs, emits strict JSON.

Invoked as `python -m agents.code_checker <task_id>` from the worktree cwd.
Requires env var EVENTS_PATH to point at the orchestrator's events.jsonl.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from shared.agent_base import (
    extract_text,
    make_bash_deny_check,
    streaming_prompt,
)
from shared.checker_utils import (
    clamp_failed_tests,
    clamp_str,
    extract_and_validate_json,
)
from shared.constants import (
    BASH_DENY,
    CHECK_TIMEOUT_SECS,
    MAX_BUILD_ERRORS_LEN,
    MAX_FAILED_TESTS,
    MAX_MESSAGE_LEN,
    MAX_TURNS,
)
from shared.prompts import CODE_CHECKER_SYSTEM_PROMPT
from src.events import emit_event
from src.project_profile import detect_project_profile
from src.tracker import Tracker


ALLOWED_TOOLS = ["Bash", "Read", "Glob"]

# Legacy aliases used by tests
_clamp_str = clamp_str
_clamp_failed_tests = clamp_failed_tests
_extract_and_validate_json = extract_and_validate_json
_extract_text = extract_text
_streaming_prompt = streaming_prompt
_can_use_tool = make_bash_deny_check(BASH_DENY)


def _events_path() -> Path:
    return Path(os.environ["EVENTS_PATH"])


def _load_task(task_id: int) -> tuple[int, str, str]:
    db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
    tracker = Tracker(db_path)
    row = tracker.get_task(task_id)
    return row.task_number, row.title, row.spec_path


def _build_user_prompt(task_id: int) -> str:
    task_number, title, spec_path = _load_task(task_id)
    profile = detect_project_profile(Path.cwd())
    return (
        f"Task number: {task_number}\n"
        f"Title: {title}\n"
        f"Project type: {profile.label}\n"
        f"Spec path: {spec_path}\n"
        "You are running inside the task's worktree. RUN_TESTS.sh is expected at "
        "./RUN_TESTS.sh in this cwd.\n"
        "Execute it per the rules in your system prompt, parse the output, and emit "
        "the strict JSON on the last line.\n"
    )


async def amain(task_id: int) -> int:
    events = _events_path()
    task_number, _title, _spec_path = _load_task(task_id)

    emit_event(events, task_id=task_number, actor="code_checker", type="started")
    emit_event(
        events,
        task_id=task_number,
        actor="code_checker",
        type="executing_tests",
        timeout_secs=CHECK_TIMEOUT_SECS,
    )

    options = ClaudeAgentOptions(
        system_prompt=CODE_CHECKER_SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="default",
        max_turns=MAX_TURNS,
        can_use_tool=_can_use_tool,
        cwd=Path.cwd(),
    )

    last_text = ""
    async for message in query(
        prompt=_streaming_prompt(_build_user_prompt(task_id)),
        options=options,
    ):
        extracted = _extract_text(message)
        if extracted:
            last_text = extracted

    parsed = extract_and_validate_json(last_text)

    if parsed["failed_tests"]:
        emit_event(
            events,
            task_id=task_number,
            actor="code_checker",
            type="tests_failed",
            fail_count=len(parsed["failed_tests"]),
        )

    emit_event(
        events,
        task_id=task_number,
        actor="code_checker",
        type="finished",
        status=parsed["status"],
    )

    print(json.dumps(parsed, ensure_ascii=False))
    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    return asyncio.run(amain(task_id))


if __name__ == "__main__":
    sys.exit(main())

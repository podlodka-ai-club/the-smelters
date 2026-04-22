"""Code checker agent. Runs RUN_TESTS.sh in the worktree, parses logs, emits strict JSON.

Invoked as `python -m agents.code_checker <task_id>` from the worktree cwd.
Requires env var EVENTS_PATH to point at the orchestrator's events.jsonl.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from src.events import emit_event
from src.project_profile import detect_project_profile
from src.tracker import Tracker


CHECK_TIMEOUT_SECS = 300
MAX_TURNS = 14
MAX_MESSAGE_LEN = 400
MAX_BUILD_ERRORS_LEN = 4000
MAX_FAILED_TESTS = 30

ALLOWED_TOOLS = ["Bash", "Read", "Glob"]

BASH_DENY = [
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bgit\s+(push|commit|reset|rebase)\b"),
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\buv\s+pip\s+install\b"),
    re.compile(r"\bsudo\b"),
]


CODE_CHECKER_SYSTEM_PROMPT = """
You are CodeChecker, a read-and-execute verification agent. Your ONLY job:
run RUN_TESTS.sh from the current working directory, observe what happens,
and emit a STRICT JSON report. You do NOT fix code, you do NOT run git, you
do NOT install packages.

Primary target: Android Gradle project (Kotlin + Jetpack Compose, multi-module
app/core/data/domain/feature under projects/DemoApp-style layouts).
Secondary target: Python projects (pytest).

Rules:
1. RUN_TESTS.sh lives at ./RUN_TESTS.sh in cwd. If it is missing, immediately
   emit failure with build_errors="RUN_TESTS.sh missing".
   If it exists but is not executable, run `chmod +x RUN_TESTS.sh` first.
2. Execute it under a hard wall-clock timeout:
     `timeout 300 bash ./RUN_TESTS.sh 2>&1 | tail -n 4000`
   Note: `timeout` exits 124 on wall-clock kill. Treat 124 as timeout=true,
   status=failed, and DO NOT retry.
3. If exit code is non-zero (and not 124), execute it EXACTLY ONE more time.
   - Retry passes -> status="passed", flaky=true.
   - Retry also fails -> status="failed", flaky=false, use second run's output.
4. Extraction heuristics (aggressive truncation -- protect the context window):

   ANDROID / GRADLE:
   - After a Gradle run, structured results live under module `build/test-results/`
     directories, e.g.:
       app/build/test-results/testDebugUnitTest/TEST-*.xml
       feature/search/build/test-results/testDebugUnitTest/TEST-*.xml
     Use Glob "**/build/test-results/**/TEST-*.xml" and parse those XMLs.
     For each <testcase> containing a <failure> or <error>, emit one entry:
       name      = "<classname>.<name>"
       message   = first line of <failure@message> or text content (<=400 chars)
       location  = fully qualified class path mapped to a test source file when
                   obvious, else "<module>/TEST-<classname>.xml"
   - Compile errors: Kotlin uses `e: /path/File.kt:LINE:COL ...` pattern;
     Java uses `/path/File.java:LINE: error: ...`; Gradle prints
     `FAILURE: Build failed with an exception.` and `* What went wrong:` blocks.
     Concatenate into build_errors (<=4000 chars, keep first occurrences).
   - OOM: grep for `java.lang.OutOfMemoryError`, `Java heap space`,
     `GC overhead limit exceeded`. Include those lines verbatim in build_errors.
   - Gradle daemon / lock issues (`Timeout waiting to lock`) -> include in
     build_errors verbatim.

   PYTHON / PYTEST (fallback):
   - Failed tests: `^FAILED (\\S+)(?:\\s+-\\s+(.+))?$` in the trailing summary.
     For each, find the corresponding `_____ name _____` block above and extract
     first 10 non-empty lines as message; location = test path::name.
   - Build/collection errors: `^ERROR ...` blocks and `ImportError`, `SyntaxError`
     tracebacks -> build_errors.

   UNIVERSAL FALLBACK:
   - If neither structured source is available: take last 100 lines of combined
     stdout/stderr, put them into build_errors verbatim.

5. HARD CAPS (enforce yourself -- do NOT rely on the outer wrapper):
   - failed_tests: max 30 entries, each message <=400 chars
   - build_errors: <=4000 chars (keep head + tail if over)
6. FORBIDDEN: modifying source, git push/commit/reset, pip/uv install, curl,
   wget, sudo, running ./gradlew tasks that mutate remote state.
7. Your VERY LAST printed line MUST be a single-line JSON object exactly:
   {"status": "<passed|failed>", "failed_tests": [{"name","message","location"}...],
    "build_errors": "...", "timeout": <bool>, "flaky": <bool>}
   No trailing prose after it.
"""


def _events_path() -> Path:
    return Path(os.environ["EVENTS_PATH"])


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


_MALFORMED: dict[str, Any] = {
    "status": "failed",
    "failed_tests": [],
    "build_errors": "malformed checker output",
    "timeout": False,
    "flaky": False,
}


def _clamp_str(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return text[:head] + text[-tail:]


def _clamp_failed_tests(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for raw in items[:MAX_FAILED_TESTS]:
        if not isinstance(raw, dict):
            continue
        out.append(
            {
                "name": _clamp_str(raw.get("name", ""), MAX_MESSAGE_LEN),
                "message": _clamp_str(raw.get("message", ""), MAX_MESSAGE_LEN),
                "location": _clamp_str(raw.get("location", ""), MAX_MESSAGE_LEN),
            }
        )
    return out


def _extract_and_validate_json(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return dict(_MALFORMED)
    candidate = lines[-1].strip()
    try:
        parsed = json.loads(candidate)
    except (ValueError, TypeError):
        return dict(_MALFORMED)
    if not isinstance(parsed, dict):
        return dict(_MALFORMED)

    status_raw = parsed.get("status")
    if status_raw not in ("passed", "failed"):
        return dict(_MALFORMED)

    return {
        "status": status_raw,
        "failed_tests": _clamp_failed_tests(parsed.get("failed_tests", [])),
        "build_errors": _clamp_str(parsed.get("build_errors", ""), MAX_BUILD_ERRORS_LEN),
        "timeout": bool(parsed.get("timeout", False)),
        "flaky": bool(parsed.get("flaky", False)),
    }


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

    parsed = _extract_and_validate_json(last_text)

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

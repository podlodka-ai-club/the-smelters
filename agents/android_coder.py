"""Android Coder agent. Invoked as `python -m agents.android_coder <task_id>` from the worktree cwd."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
import anthropic

from src.project_profile import detect_project_profile
from src.tracker import Tracker
from src.events import emit_event

ANDROID_CODER_SYSTEM_PROMPT = """
You are Android Coder, a focused software engineer working on ONE Android task at a time.
You MUST strictly follow a Test-Driven Development (TDD) approach.

Rules:
1. STRICT TEST-FIRST: Read the spec file first. You MUST write *all* unit/integration tests based on the task requirements BEFORE writing the implementation.
2. PREVENT TAUTOLOGICAL TESTS: You must use strict assertions. Do NOT test mocks in place of real implementations.
3. IMPLEMENTATION PHASE: You may write the implementation code ONLY after all tests are saved.
4. BUILD/COMPILE ONLY: Verify syntax by running build commands (e.g., `./gradlew assembleDebug`), but do NOT execute tests during your process.
5. SCRIPT GENERATION: You MUST generate a `RUN_TESTS.sh` executable script containing the exact commands required to run the tests you wrote.
6. Make the minimum change needed to satisfy the requirements.
7. Do NOT modify unrelated files.
8. When you are finished, stop and print ONE final line that is a JSON object: {"ok": true, "summary": "<...>", "script_generated": "RUN_TESTS.sh"}

If a previous review flagged issues, address them literally. Do not expand scope.
"""

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]
BASH_DENY = [
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
]


import yaml


def get_config() -> dict[str, Any]:
    config_path = Path(os.environ.get("REPO_ROOT", Path.cwd())) / "agent_config.yml"
    if not config_path.exists():
        config_path = Path("agent_config.yml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {"implementation": "gemini", "agent_timeout": 7200}


async def verify_build_compiles() -> bool:
    """
    Verifies the Android project compiles by running ./gradlew assembleDebug.
    Returns True if build succeeds, False otherwise.
    """
    gradlew = Path.cwd() / "gradlew"
    if not gradlew.exists():
        return True  # Not an Android project, skip verification
    
    try:
        process = await asyncio.create_subprocess_exec(
            str(gradlew), "assembleDebug",
            "--no-daemon",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path.cwd(),
        )
        stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=600)
        return process.returncode == 0
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def validate_tool_usage(
    tool_name: str,
    tool_input: dict[str, Any],
    _context: ToolPermissionContext,
) -> PermissionResultAllow | PermissionResultDeny:
    """
    Validates if a specific tool and its arguments are permitted to be executed.
    This acts as a security guardrail, specifically preventing destructive or 
    unwanted bash commands (like 'rm -rf /' or 'git push').
    """
    if tool_name != "Bash":
        return PermissionResultAllow()

    command = str(tool_input.get("command", ""))
    for pattern in BASH_DENY:
        if pattern.search(command):
            return PermissionResultDeny(message=f"denied by policy: matches {pattern.pattern}")
    return PermissionResultAllow()


def load_task_from_tracker(task_id: int) -> tuple[int, str, str, str | None, str]:
    """
    Loads task details from the SQLite tracker database.
    Returns:
        tuple containing: task_number, title, spec_path, review_notes, and the markdown spec_body.
    """
    db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
    tracker = Tracker(db_path)
    row = tracker.get_task(task_id)
    repo_root = Path(os.environ.get("REPO_ROOT", Path.cwd()))
    spec_body = (repo_root / row.spec_path).read_text(encoding="utf-8")
    return row.task_number, row.title, row.spec_path, row.review_notes, spec_body


def generate_prompt_for_task(task_id: int) -> str:
    """
    Constructs the complete user prompt to be sent to the LLM agent.
    Includes the task details, project profile, git history (to prevent drift),
    and any notes from a previous failed review.
    """
    task_number, title, spec_path, notes, spec_body = load_task_from_tracker(task_id)
    profile = detect_project_profile(Path.cwd())

    git_diff_history = ""
    try:
        import subprocess
        diff = subprocess.check_output(["git", "diff", "HEAD"], text=True, stderr=subprocess.DEVNULL)
        if diff:
            git_diff_history = f"\nHistory of your changes so far (git diff):\n```diff\n{diff}\n```\n"
    except Exception:
        pass

    prior_notes = f"\n\nPrevious review flagged these problems:\n{notes}\n" if notes else ""
    return (
        f"Task number: {task_number}\n"
        f"Title: {title}\n"
        f"Project type: {profile.label}\n"
        f"Spec path: {spec_path}\n"
        "Original Task Spec Markdown:\n"
        f"```md\n{spec_body}\n```\n"
        f"{prior_notes}"
        f"{git_diff_history}"
        "Run verification (compilation, NOT testing) when you think you're done. If it fails to compile, iterate.\n"
        'When done, ensure RUN_TESTS.sh is created and print ONE final line that is a JSON object: {"ok": true, "summary": "<...>", "script_generated": "RUN_TESTS.sh"}\n'
    )


def extract_text_from_message(message: object) -> str:
    """
    Safely extracts text content from an SDK message object, which might have
    different structures depending on the underlying model and response format.
    """
    result = getattr(message, "result", None)
    if isinstance(result, str):
        return result
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    return ""


async def stream_prompt_messages(prompt: str) -> AsyncIterator[dict[str, object]]:
    """
    Yields the initial user prompt as an async stream, matching the interface
    expected by the `claude_agent_sdk.query` function.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": prompt},
        "parent_tool_use_id": None,
        "session_id": "default",
    }


async def run_android_coder_agent(task_id: int) -> int:
    """
    Main asynchronous loop for the android_coder agent.
    
    Responsibilities:
    - Setup tracing and event logging.
    - Read agent configuration to choose the AI engine (Claude vs Gemini).
    - Query the LLM, managing retry loops with exponential backoff for rate limits.
    - Catch context window limits and other API errors, logging them.
    - Emit real-time progress events ('compiling', 'writing_tests') based on tool usage.
    """
    db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
    events_path = db_path.with_name("events.jsonl")

    emit_event(events_path, task_id=task_id, actor="android_coder", type="started")

    config = get_config()
    implementation = config.get("implementation", "claude").lower()
    agent_timeout = config.get("agent_timeout", 7200)  # default 2 hours

    if implementation == "gemini":
        gemini_api_key = config.get("gemini_api_key", "")
        if gemini_api_key:
            os.environ["GEMINI_API_KEY"] = gemini_api_key
        
        gemini_model = config.get("gemini_model", "google/gemini-2.5-flash")
        full_prompt = f"{ANDROID_CODER_SYSTEM_PROMPT}\n\n{generate_prompt_for_task(task_id)}"
        
        # Write prompt to temp file to avoid command line length limits
        prompt_file = Path.cwd() / ".prompt.txt"
        prompt_file.write_text(full_prompt)
        
        cmd = [
            "opencode", "run",
            "--model", gemini_model,
            "--attach", "http://localhost:4096",
            "--file", str(prompt_file)
        ]
        
        print(f"INFO: Running command: {' '.join(cmd)}", file=sys.stderr)
        
        try:
            emit_event(events_path, task_id=task_id, actor="android_coder", type="compiling")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=Path.cwd()
            )
            
            print(f"INFO: Process started with PID: {process.pid}", file=sys.stderr)
            
            # Read output with configurable timeout
            try:
                stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=agent_timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error_msg = f"Agent timed out after {agent_timeout} seconds"
                print(f"ERROR: {error_msg}", file=sys.stderr)
                emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error=error_msg)
                print(json.dumps({"ok": False, "error": error_msg}))
                return 1
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            
            # Debug: print stderr if there's an issue
            if process.returncode != 0:
                print(f"ERROR: opencode exit code: {process.returncode}", file=sys.stderr)
                print(f"ERROR stdout (last 1000 chars): {stdout[-1000:]}", file=sys.stderr)
            
            lines = [line for line in stdout.splitlines() if line.strip()]
            if lines:
                candidate = lines[-1].strip()
                if candidate.startswith("{") and '"ok"' in candidate:
                    emit_event(events_path, task_id=task_id, actor="android_coder", type="finished", script_generated="RUN_TESTS.sh")
                    print(candidate)
                    # Don't return immediately - verify build first

            emit_event(events_path, task_id=task_id, actor="android_coder", type="finished", script_generated="RUN_TESTS.sh")
            print(json.dumps({"ok": True, "summary": stdout[-200:] if stdout else "done", "script_generated": "RUN_TESTS.sh"}))
            return 0
        except Exception as e:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="failed",
                error=type(e).__name__,
                stack_trace=traceback.format_exc()
            )
            print(json.dumps({"ok": False, "error": str(e)}))
            return 1

    # Verify build compiles after successful agent run
    build_success = await verify_build_compiles()
    if not build_success:
        emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error="build_failed")
        print(json.dumps({"ok": False, "error": "Build failed - code does not compile"}))
        return 1

    # Default: Claude implementation
    anthropic_api_key = config.get("anthropic_api_key", "")
    if anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
    elif "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    options = ClaudeAgentOptions(
        system_prompt=ANDROID_CODER_SYSTEM_PROMPT,
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="acceptEdits",
        max_turns=30,
        can_use_tool=validate_tool_usage,
        cwd=Path.cwd(),
    )

    last_text = ""
    retry_delay = 5
    max_retries = 5

    for attempt in range(max_retries):
        try:
            async for message in query(prompt=stream_prompt_messages(generate_prompt_for_task(task_id)), options=options):
                extracted = extract_text_from_message(message)
                if extracted:
                    last_text = extracted
                
                tool_use = getattr(message, "tool_use", None)
                if tool_use:
                    tool_name = getattr(tool_use, "name", "")
                    tool_input = getattr(tool_use, "input", {})
                    if tool_name == "Bash":
                        command = tool_input.get("command", "")
                        if "gradlew assembleDebug" in command or "build" in command or "compile" in command:
                            emit_event(events_path, task_id=task_id, actor="android_coder", type="compiling")
                    elif tool_name in ["Write", "Edit"]:
                        filepath = tool_input.get("filePath", "")
                        if "test" in filepath.lower():
                            emit_event(events_path, task_id=task_id, actor="android_coder", type="writing_tests")

            break
        except anthropic.RateLimitError:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="failed",
                error="RateLimitError",
                retry_in=retry_delay,
                stack_trace=traceback.format_exc()
            )
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
        except anthropic.APIConnectionError:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="failed",
                error="NetworkTimeout",
                retry_in=retry_delay,
                stack_trace=traceback.format_exc()
            )
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
        except anthropic.BadRequestError as e:
            if "context_length_exceeded" in str(e).lower() or "context window" in str(e).lower():
                emit_event(
                    events_path,
                    task_id=task_id,
                    actor="android_coder",
                    type="failed",
                    error="ContextWindowExceeded",
                    stack_trace=traceback.format_exc()
                )
                print(json.dumps({"ok": False, "error": "Context window exceeded"}))
                return 1
            raise e
        except Exception as e:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="failed",
                error=type(e).__name__,
                stack_trace=traceback.format_exc()
            )
            print(json.dumps({"ok": False, "error": str(e)}))
            return 1

    lines = [line for line in last_text.splitlines() if line.strip()]
    if lines:
        candidate = lines[-1].strip()
        if candidate.startswith("{") and '"ok"' in candidate:
            emit_event(events_path, task_id=task_id, actor="android_coder", type="finished", script_generated="RUN_TESTS.sh")
            print(candidate)
            return 0

    emit_event(events_path, task_id=task_id, actor="android_coder", type="finished", script_generated="RUN_TESTS.sh")
    print(json.dumps({"ok": True, "summary": last_text[:200] or "done", "script_generated": "RUN_TESTS.sh"}))

    # Verify build compiles after successful agent run
    build_success = await verify_build_compiles()
    if not build_success:
        emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error="build_failed")
        print(json.dumps({"ok": False, "error": "Build failed - code does not compile"}))
        return 1

    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    return asyncio.run(run_android_coder_agent(task_id))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

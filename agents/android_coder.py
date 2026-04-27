"""Android Coder agent. Invoked as `python -m agents.android_coder <task_id>` from the worktree cwd."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import traceback
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext
import anthropic

from shared.constants import BASH_DENY
from shared.prompts import ANDROID_CODER_SYSTEM_PROMPT
from src.project_profile import detect_project_profile
from src.tracker import Tracker
from src.events import emit_event
from src.worktree import ensure_task_worktree_dir

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Bash"]


import yaml

HEARTBEAT_INTERVAL_SECONDS = 30
WATCHDOG_POLL_SECONDS = 5

OPENCODE_ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("location_unsupported", re.compile(r"user location is not supported", re.IGNORECASE)),
    ("rate_limit", re.compile(r"\bquota\b|rate limit|\b429\b", re.IGNORECASE)),
    ("network", re.compile(r"connection|timed out|econnreset", re.IGNORECASE)),
    ("auth", re.compile(r"unauthorized|authentication", re.IGNORECASE)),
]


def get_config() -> dict[str, Any]:
    config_path = Path(os.environ.get("REPO_ROOT", Path.cwd())) / "agent_config.yml"
    if not config_path.exists():
        config_path = Path("agent_config.yml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {
        "implementation": "gemini",
        "agent_timeout": 7200,
        "agent_inactivity_timeout": 600,
    }


def redact_env_snapshot() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for key in ("PATH", "HOME", "LANG"):
        value = os.environ.get(key)
        if value:
            snapshot[key] = value
    for key, value in os.environ.items():
        if key.startswith("OPENCODE_"):
            snapshot[key] = value
    return snapshot


def detect_opencode_error_category(line: str) -> str | None:
    for category, pattern in OPENCODE_ERROR_PATTERNS:
        if pattern.search(line):
            return category
    return None


def get_opencode_version() -> str:
    try:
        result = subprocess.run(
            ["opencode", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "unknown"
        return f"error_exit_{result.returncode}"
    except Exception as exc:
        return f"error:{type(exc).__name__}"


def get_server_health() -> str:
    try:
        with urlopen("http://localhost:4096/health", timeout=2) as response:
            return f"http_{response.status}"
    except URLError as exc:
        reason = getattr(exc, "reason", "unreachable")
        return f"unreachable:{reason}"
    except Exception as exc:
        return f"error:{type(exc).__name__}"


def _opencode_db_path() -> Path:
    override = os.environ.get("OPENCODE_DB_PATH")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def recover_output_from_opencode_db(*, cwd: Path, started_at_ms: int) -> str:
    """
    Recover assistant output from opencode's sqlite DB when CLI stdout is silent.
    This is a best-effort fallback for known non-interactive buffering/hang issues.
    """
    db_path = _opencode_db_path()
    if not db_path.exists():
        return ""

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception:
        return ""

    try:
        # Allow a 2 minute skew to catch sessions created slightly before run start.
        lower_bound = started_at_ms - 120_000
        session_row = conn.execute(
            "SELECT id FROM session WHERE directory=? AND time_created>=? "
            "ORDER BY time_created DESC LIMIT 1",
            (str(cwd), lower_bound),
        ).fetchone()
        if not session_row:
            return ""
        session_id = str(session_row[0])

        rows = conn.execute(
            "SELECT data FROM part WHERE session_id=? ORDER BY time_created ASC",
            (session_id,),
        ).fetchall()
    except Exception:
        return ""
    finally:
        conn.close()

    chunks: list[str] = []
    for (raw_data,) in rows:
        if not raw_data:
            continue
        try:
            payload = json.loads(raw_data)
        except Exception:
            continue

        part_type = payload.get("type")
        if part_type in {"text", "reasoning"}:
            text = payload.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
        elif part_type == "tool":
            state = payload.get("state")
            if isinstance(state, dict):
                output = state.get("output")
                if isinstance(output, str) and output.strip():
                    chunks.append(output)

    return "\n".join(chunks)


async def verify_build_compiles(
    events_path: Path | None = None,
    task_id: int | None = None,
) -> bool:
    """
    Verifies the Android project compiles by running ./gradlew assembleDebug.
    Returns True if build succeeds, False otherwise.
    """
    gradlew = Path.cwd() / "gradlew"
    if not gradlew.exists():
        return True  # Not an Android project, skip verification
    
    if events_path:
        emit_event(
            events_path,
            task_id=task_id,
            actor="android_coder",
            type="compile_started",
            command="./gradlew assembleDebug --no-daemon",
            cwd=str(Path.cwd()),
        )

    try:
        process = await asyncio.create_subprocess_exec(
            str(gradlew), "assembleDebug",
            "--no-daemon",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path.cwd(),
        )

        assert process.stdout is not None
        output_lines: list[str] = []

        async def stream_compile_output() -> None:
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                output_lines.append(line)
                if events_path:
                    emit_event(
                        events_path,
                        task_id=task_id,
                        actor="android_coder",
                        type="compile_output",
                        line=line,
                    )

        await asyncio.wait_for(
            asyncio.gather(stream_compile_output(), process.wait()),
            timeout=600,
        )

        if events_path:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="compile_finished",
                returncode=process.returncode,
            )
        return process.returncode == 0
    except asyncio.TimeoutError:
        if events_path:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="compile_timeout",
                timeout_seconds=600,
            )
        return False
    except Exception:
        if events_path:
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="compile_exception",
                error="unexpected_exception",
            )
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


def extract_success_json_from_output(output: str) -> dict[str, Any] | None:
    """
    Extracts success JSON from mixed stdout/stderr output.
    Scans lines from bottom-up and validates required success keys.
    """
    # First, try extracting JSON objects spanning multiple lines.
    json_candidates = re.findall(r"\{[\s\S]*?\}", output)
    for candidate in reversed(json_candidates):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        if payload.get("ok") is True and payload.get("script_generated") == "RUN_TESTS.sh":
            return payload

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        candidates = [line]
        inline_match = re.search(r"(\{.*\})", line)
        if inline_match:
            candidates.append(inline_match.group(1))

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            if payload.get("ok") is True and payload.get("script_generated") == "RUN_TESTS.sh":
                return payload

    return None


def _resolve_task_worktree_and_chdir(task_id: int, db_path: Path) -> Path:
    """Chdir into the task sandbox under worktrees/ (never ``projects/<project>``)."""
    repo_root = Path(os.environ.get("REPO_ROOT", os.getcwd())).resolve()
    tracker = Tracker(db_path)
    path, _ = ensure_task_worktree_dir(
        repo_root=repo_root,
        tracker=tracker,
        task_id=task_id,
        db_path=db_path,
        project=None,
    )
    os.chdir(path)
    return path


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

    task_worktree = _resolve_task_worktree_and_chdir(task_id, db_path)

    config = get_config()
    implementation = config.get("implementation", "claude").lower()
    agent_timeout = config.get("agent_timeout", 7200)  # default 2 hours
    inactivity_timeout = config.get("agent_inactivity_timeout", 600)

    if implementation == "gemini":
        gemini_api_key = config.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
        if gemini_api_key:
            os.environ["GEMINI_API_KEY"] = gemini_api_key
            os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = gemini_api_key
        
        gemini_model = config.get("gemini_model", "google/gemini-2.5-flash")
        opencode_provider = f"opencode/{gemini_model}"
        full_prompt = f"{ANDROID_CODER_SYSTEM_PROMPT}\n\n{generate_prompt_for_task(task_id)}"

        prompt_file_abs = task_worktree / ".prompt.txt"
        prompt_file_abs.write_text(full_prompt)
        opencode_message = "Implement the task exactly as described in the attached prompt file."
        
        server_url = config.get("opencode_server_url", "")
        cmd = ["opencode", "run", "--model", gemini_model]
        if server_url:
            cmd += ["--attach", server_url]
        cmd += ["--dir", str(task_worktree), opencode_message, "--file", str(prompt_file_abs)]
        
        print(f"INFO: Running command: {' '.join(cmd)}", file=sys.stderr)
        print(f"INFO: Working directory: {task_worktree}", file=sys.stderr)
        
        process: asyncio.subprocess.Process | None = None
        try:
            pre_run_head = None
            try:
                pre_run_head = (
                    await asyncio.create_subprocess_exec(
                        "git",
                        "rev-parse",
                        "HEAD",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        cwd=task_worktree,
                    )
                )
                pre_run_head_out, _ = await pre_run_head.communicate()
                pre_run_sha = pre_run_head_out.decode("utf-8", errors="replace").strip() or None
            except Exception:
                pre_run_sha = None

            server_health = get_server_health()
            opencode_version = get_opencode_version()
            if server_health != "http_200":
                error_message = (
                    "opencode serve not reachable on http://localhost:4096; "
                    "start it with: opencode serve --port 4096 &"
                )
                emit_event(
                    events_path,
                    task_id=task_id,
                    actor="android_coder",
                    type="failed",
                    error="opencode_serve_unreachable",
                    server_health=server_health,
                    message=error_message,
                )
                print(json.dumps({"ok": False, "error": error_message}))
                return 1

            emit_event(events_path, task_id=task_id, actor="android_coder", type="agent_running", provider=opencode_provider)
            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="agent_launch",
                provider=opencode_provider,
                cmd=cmd,
                cwd=str(task_worktree),
                model=gemini_model,
                attach="http://localhost:4096",
                opencode_version=opencode_version,
                server_health=server_health,
                env=redact_env_snapshot(),
            )
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=task_worktree,
            )
            
            print(f"INFO: Process started with PID: {process.pid}", file=sys.stderr)
            
            # Read output with configurable timeout and stream lines to the event log.
            stdout = ""
            start_monotonic = time.monotonic()
            start_wall_ms = int(time.time() * 1000)
            last_output_at = start_monotonic
            output_lines_count = 0
            last_output_line_preview = ""
            inactivity_timed_out = False
            try:
                if process.stdout is not None:
                    output_chunks: list[str] = []

                    async def stream_agent_output() -> None:
                        nonlocal last_output_at, output_lines_count, last_output_line_preview
                        pending_text = ""
                        while True:
                            chunk = await process.stdout.read(1024)
                            if not chunk:
                                break
                            chunk_text = chunk.decode("utf-8", errors="replace")
                            output_chunks.append(chunk_text)
                            last_output_at = time.monotonic()
                            pending_text += chunk_text

                            # Emit complete lines when available, but still keep heartbeats alive
                            # if the process writes partial lines only.
                            while "\n" in pending_text:
                                line, pending_text = pending_text.split("\n", 1)
                                output_lines_count += 1
                                last_output_line_preview = line[:300]
                                emit_event(
                                    events_path,
                                    task_id=task_id,
                                    actor="android_coder",
                                    type="agent_output_line",
                                    provider=opencode_provider,
                                    line=line,
                                )
                                error_category = detect_opencode_error_category(line)
                                if error_category:
                                    emit_event(
                                        events_path,
                                        task_id=task_id,
                                        actor="android_coder",
                                        type="opencode_error_detected",
                                        category=error_category,
                                        line=line[:500],
                                    )

                        # Flush any trailing non-newline chunk as a final line for observability.
                        trailing = pending_text.strip()
                        if trailing:
                            output_lines_count += 1
                            last_output_line_preview = trailing[:300]
                            emit_event(
                                events_path,
                                task_id=task_id,
                                actor="android_coder",
                                type="agent_output_line",
                                provider=opencode_provider,
                                line=trailing,
                            )
                            error_category = detect_opencode_error_category(trailing)
                            if error_category:
                                emit_event(
                                    events_path,
                                    task_id=task_id,
                                    actor="android_coder",
                                    type="opencode_error_detected",
                                    category=error_category,
                                    line=trailing[:500],
                                )

                    async def emit_heartbeat() -> None:
                        while process.returncode is None:
                            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                            if process.returncode is not None:
                                break
                            now = time.monotonic()
                            emit_event(
                                events_path,
                                task_id=task_id,
                                actor="android_coder",
                                type="agent_heartbeat",
                                provider=opencode_provider,
                                seconds_running=int(now - start_monotonic),
                                seconds_since_last_output=int(now - last_output_at),
                                output_lines_count=output_lines_count,
                            )

                    async def inactivity_watchdog() -> None:
                        nonlocal inactivity_timed_out
                        while process.returncode is None:
                            await asyncio.sleep(WATCHDOG_POLL_SECONDS)
                            now = time.monotonic()
                            if now - last_output_at >= inactivity_timeout:
                                inactivity_timed_out = True
                                if process.returncode is None:
                                    process.kill()
                                break

                    stream_task = asyncio.create_task(stream_agent_output())
                    heartbeat_task = asyncio.create_task(emit_heartbeat())
                    watchdog_task = asyncio.create_task(inactivity_watchdog())
                    try:
                        await asyncio.wait_for(process.wait(), timeout=agent_timeout)
                        await asyncio.wait_for(stream_task, timeout=10)
                    finally:
                        heartbeat_task.cancel()
                        watchdog_task.cancel()
                        await asyncio.gather(heartbeat_task, watchdog_task, return_exceptions=True)
                        if not stream_task.done():
                            stream_task.cancel()
                            await asyncio.gather(stream_task, return_exceptions=True)

                    if inactivity_timed_out:
                        now = time.monotonic()
                        inactivity_seconds = int(now - last_output_at)
                        recovered_output = recover_output_from_opencode_db(
                            cwd=task_worktree,
                            started_at_ms=start_wall_ms,
                        )
                        recovered_success = extract_success_json_from_output(recovered_output) if recovered_output else None
                        if recovered_success:
                            if os.environ.get("SKIP_RUN_TESTS_CHECK") != "1" and not (task_worktree / "RUN_TESTS.sh").exists():
                                emit_event(
                                    events_path,
                                    task_id=task_id,
                                    actor="android_coder",
                                    type="failed",
                                    error="missing_run_tests_sh_after_recovery",
                                    recovered_output_chars=len(recovered_output),
                                )
                                print(json.dumps({"ok": False, "error": "RUN_TESTS.sh was not created"}))
                                return 1
                            emit_event(
                                events_path,
                                task_id=task_id,
                                actor="android_coder",
                                type="finished",
                                script_generated="RUN_TESTS.sh",
                                recovered_from_db=True,
                                recovered_output_chars=len(recovered_output),
                            )
                            print(json.dumps(recovered_success))
                            return 0
                        emit_event(
                            events_path,
                            task_id=task_id,
                            actor="android_coder",
                            type="failed",
                            error="inactivity_timeout",
                            inactivity_seconds=inactivity_seconds,
                            seconds_running=int(now - start_monotonic),
                            output_lines_count=output_lines_count,
                            last_output_line_preview=last_output_line_preview,
                            recovered_output_chars=len(recovered_output),
                        )
                        print(json.dumps({"ok": False, "error": f"Agent inactive for {inactivity_seconds} seconds"}))
                        return 1

                    stdout = "".join(output_chunks)
                else:
                    # Fallback path for mocked processes in tests.
                    stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=agent_timeout)
                    stdout = stdout_bytes.decode("utf-8", errors="replace")
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error_msg = f"Agent timed out after {agent_timeout} seconds"
                recovered_output = recover_output_from_opencode_db(
                    cwd=task_worktree,
                    started_at_ms=start_wall_ms,
                )
                recovered_success = extract_success_json_from_output(recovered_output) if recovered_output else None
                if recovered_success:
                    if os.environ.get("SKIP_RUN_TESTS_CHECK") != "1" and not (task_worktree / "RUN_TESTS.sh").exists():
                        emit_event(
                            events_path,
                            task_id=task_id,
                            actor="android_coder",
                            type="failed",
                            error="missing_run_tests_sh_after_timeout_recovery",
                            recovered_output_chars=len(recovered_output),
                        )
                        print(json.dumps({"ok": False, "error": "RUN_TESTS.sh was not created"}))
                        return 1
                    emit_event(
                        events_path,
                        task_id=task_id,
                        actor="android_coder",
                        type="finished",
                        script_generated="RUN_TESTS.sh",
                        recovered_from_db=True,
                        recovered_output_chars=len(recovered_output),
                    )
                    print(json.dumps(recovered_success))
                    return 0
                print(f"ERROR: {error_msg}", file=sys.stderr)
                now = time.monotonic()
                emit_event(
                    events_path,
                    task_id=task_id,
                    actor="android_coder",
                    type="failed",
                    error=error_msg,
                    seconds_running=int(now - start_monotonic),
                    output_lines_count=output_lines_count,
                    last_output_line_preview=last_output_line_preview,
                    recovered_output_chars=len(recovered_output),
                )
                print(json.dumps({"ok": False, "error": error_msg}))
                return 1
            except asyncio.CancelledError:
                if process and process.returncode is None:
                    process.kill()
                    await process.wait()
                now = time.monotonic()
                emit_event(
                    events_path,
                    task_id=task_id,
                    actor="android_coder",
                    type="failed",
                    error="interrupted",
                    seconds_running=int(now - start_monotonic),
                    output_lines_count=output_lines_count,
                    last_output_line_preview=last_output_line_preview,
                )
                print(json.dumps({"ok": False, "error": "Interrupted"}))
                return 130

            emit_event(
                events_path,
                task_id=task_id,
                actor="android_coder",
                type="agent_output",
                provider=opencode_provider,
                output=stdout,
            )
            
            # Check for non-zero exit code
            if process.returncode != 0:
                print(f"ERROR: opencode exit code: {process.returncode}", file=sys.stderr)
                print(f"ERROR stdout (last 1000 chars): {stdout[-1000:]}", file=sys.stderr)
                # Check if killed by signal (e.g., -9 = SIGKILL)
                if process.returncode < 0:
                    now = time.monotonic()
                    emit_event(
                        events_path,
                        task_id=task_id,
                        actor="android_coder",
                        type="failed",
                        error="killed_by_signal",
                        seconds_running=int(now - start_monotonic),
                        output_lines_count=output_lines_count,
                        last_output_line_preview=last_output_line_preview,
                    )
                    print(json.dumps({"ok": False, "error": f"Agent killed by signal {abs(process.returncode)}"}))
                    return 1
                # Non-zero exit means failure - don't check for RUN_TESTS.sh
                now = time.monotonic()
                emit_event(
                    events_path,
                    task_id=task_id,
                    actor="android_coder",
                    type="failed",
                    error="non_zero_exit",
                    seconds_running=int(now - start_monotonic),
                    output_lines_count=output_lines_count,
                    last_output_line_preview=last_output_line_preview,
                )
                print(json.dumps({"ok": False, "error": f"Agent exited with code {process.returncode}"}))
                return 1

            # Protect branch history: this run must not auto-commit.
            if pre_run_sha:
                try:
                    post_run_head = await asyncio.create_subprocess_exec(
                        "git",
                        "rev-parse",
                        "HEAD",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        cwd=task_worktree,
                    )
                    post_run_head_out, _ = await post_run_head.communicate()
                    post_run_sha = post_run_head_out.decode("utf-8", errors="replace").strip() or None
                    if post_run_sha and post_run_sha != pre_run_sha:
                        now = time.monotonic()
                        emit_event(
                            events_path,
                            task_id=task_id,
                            actor="android_coder",
                            type="failed",
                            error="auto_commit_detected",
                            seconds_running=int(now - start_monotonic),
                            output_lines_count=output_lines_count,
                            last_output_line_preview=last_output_line_preview,
                        )
                        print(json.dumps({"ok": False, "error": "Auto commit detected; commits are not allowed"}))
                        return 1
                except Exception:
                    pass
            # Only check for success if exit code is 0
            success_payload = extract_success_json_from_output(stdout)
            if success_payload:
                # Check if RUN_TESTS.sh was actually created (skip in tests)
                if os.environ.get("SKIP_RUN_TESTS_CHECK") != "1" and not (task_worktree / "RUN_TESTS.sh").exists():
                    emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error="missing_run_tests_sh")
                    print(json.dumps({"ok": False, "error": "RUN_TESTS.sh was not created"}))
                    return 1
                # Success - RUN_TESTS.sh exists
                emit_event(events_path, task_id=task_id, actor="android_coder", type="finished", script_generated="RUN_TESTS.sh")
                print(json.dumps(success_payload))
            elif os.environ.get("SKIP_RUN_TESTS_CHECK") == "1":
                # In tests, allow non-JSON output when exit code is 0
                print(stdout[-200:] if stdout else "done")
            else:
                # Agent didn't return success JSON
                now = time.monotonic()
                emit_event(
                    events_path,
                    task_id=task_id,
                    actor="android_coder",
                    type="failed",
                    error="no_success_json",
                    seconds_running=int(now - start_monotonic),
                    output_lines_count=output_lines_count,
                    last_output_line_preview=last_output_line_preview,
                )
                print(json.dumps({"ok": False, "error": "Agent did not return success JSON"}))
                return 1
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

        # Verify build compiles after successful Gemini run
        build_success = await verify_build_compiles(events_path=events_path, task_id=task_id)
        if not build_success:
            emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error="build_failed")
            print(json.dumps({"ok": False, "error": "Build failed - code does not compile"}))
            return 1
        return 0

    # Default: Claude implementation
    anthropic_api_key = config.get("anthropic_api_key", "")
    if anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key
    elif "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    emit_event(
        events_path,
        task_id=task_id,
        actor="android_coder",
        type="agent_launch",
        provider="claude",
        cmd=["claude_agent_sdk.query"],
        cwd=str(Path.cwd()),
        model="claude_agent_sdk_default",
        attach=None,
        opencode_version=None,
        server_health=None,
        env=redact_env_snapshot(),
    )

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
                    emit_event(
                        events_path,
                        task_id=task_id,
                        actor="android_coder",
                        type="agent_output",
                        provider="claude",
                        output=extracted,
                    )
                
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
    build_success = await verify_build_compiles(events_path=events_path, task_id=task_id)
    if not build_success:
        emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error="build_failed")
        print(json.dumps({"ok": False, "error": "Build failed - code does not compile"}))
        return 1

    return 0


def main() -> int:
    task_id = int(sys.argv[1])
    try:
        return asyncio.run(run_android_coder_agent(task_id))
    except KeyboardInterrupt:
        db_path = Path(os.environ.get("TRACKER_DB", "tasks.db"))
        events_path = db_path.with_name("events.jsonl")
        emit_event(events_path, task_id=task_id, actor="android_coder", type="failed", error="keyboard_interrupt")
        print(json.dumps({"ok": False, "error": "Interrupted by user"}))
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

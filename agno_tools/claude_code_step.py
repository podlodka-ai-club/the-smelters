"""Custom Agno Workflow steps that delegate phases to `claude -p`.

Lets us reuse Claude Code's subscription auth + bundled tools (Read/Write/Edit/Bash/
Skills/MCP) instead of going through the Anthropic API directly. Two factories:

- `make_claude_code_coder_step`   — coder phase (writes tests + impl + RUN_TESTS.sh)
- `make_claude_code_checker_step` — checker phase (runs RUN_TESTS.sh, emits JSON)

The contracts match the Agno-Agent versions:
  coder   → output ends with {"ok": true, "summary": "...", "script_generated": "RUN_TESTS.sh"}
  checker → output ends with {"status": "passed|failed", "failed_tests": [...], ...}

Trade-offs vs an Agno-native Agent:
- ✓ no ANTHROPIC_API_KEY required if Claude Code is logged in
- ✓ Claude Code's full agent loop (its tools, skills, MCP) instead of our BashTool
- ✗ token usage doesn't roll up into Agno's SessionMetrics (claude-cli prints its own)
- ✗ we can't intercept individual tool calls — we only see final stdout
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agno.workflow.types import StepInput, StepOutput

from agno_agents.android_coder import ANDROID_CODER_SYSTEM_PROMPT
from agno_agents.code_checker import CODE_CHECKER_SYSTEM_PROMPT


# Module-level accumulator for claude-cli cost USD per run. The orchestrator's
# run_with_metrics resets it before the workflow and reads it after, so it can
# fold claude-cli spend into the Run Summary alongside Agno's SessionMetrics.
_RUN_COSTS_USD: List[Tuple[str, float]] = []


def reset_claude_run_costs() -> None:
    """Clear the per-run cost accumulator. Call before invoking a workflow."""
    _RUN_COSTS_USD.clear()


def get_claude_run_costs() -> List[Tuple[str, float]]:
    """Returns [(label, usd), ...] of every claude-cli invocation since last reset."""
    return list(_RUN_COSTS_USD)


def _resolve_claude_bin() -> str:
    """Honor $CLAUDE_BIN env override; otherwise rely on PATH lookup."""
    override = os.environ.get("CLAUDE_BIN")
    if override:
        return override
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (
        Path.home() / ".local" / "bin" / "claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
    ):
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        "claude CLI not found on PATH. Install Claude Code or set $CLAUDE_BIN."
    )


def _build_user_prompt_for_coder(task_content: str, feedback: str) -> str:
    """Compose the per-iteration coder message. On iteration 2+ the prior checker JSON
    flows in as `feedback` (Loop's forward_iteration_output=True)."""
    parts = ["<TASK>", task_content.strip(), "</TASK>"]
    if feedback and '"status"' in feedback:
        parts += [
            "",
            "<PREVIOUS_FAILURE>",
            "The CodeChecker ran your previous attempt and reported the following.",
            "Address `failed_tests` and `build_errors` literally; do not expand scope.",
            feedback.strip(),
            "</PREVIOUS_FAILURE>",
        ]
    parts += [
        "",
        "Follow the rules in your system prompt strictly.",
        "When done — and only after running the verify steps in Rule 6 — print",
        'one final JSON line: {"ok": true, "summary": "...", "script_generated": "RUN_TESTS.sh"}',
    ]
    return "\n".join(parts)


_CHECKER_USER_PROMPT = (
    "Run RUN_TESTS.sh per your system prompt rules. The script lives at "
    "`./RUN_TESTS.sh` in the current working directory. Parse the output, find "
    "`**/build/test-results/**/TEST-*.xml`, and emit the strict JSON on the very "
    "last line as specified."
)


def _truncate(text: str, n: int = 160) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def _format_tool_use(name: str, inp: Dict[str, Any]) -> str:
    """Compact one-liner for an assistant's tool_use block."""
    if not inp:
        return f"{name}()"
    primary_keys = ("command", "file_path", "filePath", "path", "pattern", "url", "query")
    for key in primary_keys:
        if key in inp:
            return f"{name}({key}={_truncate(str(inp[key]), 140)})"
    first_key = next(iter(inp))
    return f"{name}({first_key}={_truncate(str(inp[first_key]), 140)})"


def _format_tool_result(content: Any) -> str:
    """Compact one-liner for a tool_result block."""
    if isinstance(content, str):
        return _truncate(content)
    if isinstance(content, list):
        joined = " ".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
        return _truncate(joined)
    return _truncate(str(content))


def _stream_claude_events(
    process: subprocess.Popen,
    label: str,
) -> Tuple[str, Optional[float]]:
    """Read stream-json events line-by-line, pretty-print live, return (final_text, cost_usd).

    The final assistant text comes from the `result` event when present, otherwise
    accumulated from `assistant`-message text blocks during the run.
    """
    accumulated_text: List[str] = []
    final_result_text: Optional[str] = None
    cost_usd: Optional[float] = None
    text_in_progress = False  # inside an unterminated streaming text delta

    def write(line: str) -> None:
        sys.stdout.write(f"  │ {line}\n")
        sys.stdout.flush()

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            write(f"(raw) {_truncate(line, 200)}")
            continue

        ev_type = event.get("type")

        if ev_type == "system":
            subtype = event.get("subtype")
            if subtype == "init":
                model = event.get("model") or "?"
                sid = (event.get("session_id") or "?")[:8]
                write(f"[start] model={model} session={sid}")
            # else: hook_started / hook_response / status / etc. — pure noise, skip
            continue

        if ev_type == "rate_limit_event":
            # Throttle/rate-limit telemetry — informational, skip from terminal.
            continue

        if ev_type in {"stream_event", "content_block_delta"}:
            # --include-partial-messages emits these between full assistant blocks;
            # they carry partial text deltas. Print as they come (still useful).
            delta = event.get("delta") or event.get("event", {}).get("delta") or {}
            if isinstance(delta, dict) and delta.get("type") == "text_delta":
                fragment = delta.get("text", "")
                if fragment:
                    sys.stdout.write(fragment if text_in_progress else f"  │ {fragment}")
                    text_in_progress = not fragment.endswith("\n")
                    sys.stdout.flush()
                    accumulated_text.append(fragment)
            continue

        if ev_type == "assistant":
            content = event.get("message", {}).get("content", []) or []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text = block.get("text", "")
                    if text:
                        accumulated_text.append(text)
                        for chunk in text.splitlines() or [text]:
                            if chunk:
                                write(chunk)
                elif btype == "tool_use":
                    write(f"→ {_format_tool_use(block.get('name', '?'), block.get('input', {}))}")
            continue

        if ev_type == "user":
            content = event.get("message", {}).get("content", []) or []
            for block in content:
                if block.get("type") == "tool_result":
                    is_error = bool(block.get("is_error"))
                    arrow = "←✗" if is_error else "←"
                    write(f"{arrow} {_format_tool_result(block.get('content', ''))}")
            continue

        if ev_type == "result":
            if text_in_progress:
                sys.stdout.write("\n")
                text_in_progress = False
            sub = event.get("subtype")
            res = event.get("result")
            if isinstance(res, str):
                final_result_text = res
            cost_usd = event.get("total_cost_usd") or event.get("cost_usd")
            if cost_usd is not None:
                write(f"[result] subtype={sub} cost=${cost_usd:.4f}")
            else:
                write(f"[result] subtype={sub}")
            continue

        # Defensive: unknown event types — show type + summary so we notice format drift
        write(f"({ev_type}) {_truncate(line, 160)}")

    if text_in_progress:
        sys.stdout.write("\n")
        sys.stdout.flush()

    final_text = final_result_text if final_result_text is not None else "".join(accumulated_text)
    return final_text, cost_usd


def _run_claude_p(
    *,
    cwd: str,
    system_prompt: str,
    user_prompt: str,
    model_alias: str,
    timeout_secs: int,
    max_budget_usd: Optional[float],
    allowed_tools: Optional[List[str]] = None,
    disallowed_tools: Optional[List[str]] = None,
    label: str = "claude",
) -> StepOutput:
    """Shared runner: shells out to `claude -p` with stream-json output and pretty-prints
    every event to our terminal in real time. Returns StepOutput whose content is the
    final assistant text (so `_parse_checker_status` etc. can find their JSON line).

    A daemon watchdog thread enforces `timeout_secs`.
    """
    claude_bin = _resolve_claude_bin()
    cmd: List[str] = [
        claude_bin,
        "-p",
        # stream-json + --include-partial-messages is the only way to get real-time
        # output when stdout is piped. text mode buffers everything to the end.
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--verbose",            # required by claude when using stream-json + --print
        # bypassPermissions auto-approves ALL tool invocations. acceptEdits was too
        # narrow — it allowed Edit/Write but blocked Bash with pipes/`&&`/`2>&1`,
        # and our coder needs to run `./gradlew :module:assembleDebug --quiet 2>&1`
        # to verify compilation. The system prompt forbids destructive ops, and
        # cwd is pinned to the project root, so the blast radius is bounded.
        "--permission-mode", "bypassPermissions",
        "--model", model_alias,
        "--system-prompt", system_prompt,
        "--no-session-persistence",
    ]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if disallowed_tools:
        cmd += ["--disallowedTools", ",".join(disallowed_tools)]
    if max_budget_usd is not None:
        cmd += ["--max-budget-usd", str(max_budget_usd)]
    # IMPORTANT: --allowedTools / --disallowedTools are declared as variadic
    # (`<tools...>`) in claude's CLI (commander.js). Even comma-separated values
    # are still variadic — the parser greedily eats every following argv element.
    # `--` is the universal "end of options" marker; everything after it is
    # treated as positional, so our prompt can't be misinterpreted as a tool name.
    cmd += ["--", user_prompt]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,           # line-buffered
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        return StepOutput(content=f'{{"ok": false, "error": "claude not runnable: {exc}"}}')

    timed_out = {"flag": False}

    def _watchdog() -> None:
        time.sleep(timeout_secs)
        if process.poll() is None:
            timed_out["flag"] = True
            process.kill()

    threading.Thread(target=_watchdog, daemon=True).start()

    sys.stdout.write(f"\n  ╭─ [{label}] live (timeout {timeout_secs}s):\n")
    sys.stdout.flush()

    final_text = ""
    cost = None
    try:
        final_text, cost = _stream_claude_events(process, label)
        process.wait()
    except KeyboardInterrupt:
        process.kill()
        process.wait(timeout=5)
        raise
    finally:
        if isinstance(cost, (int, float)):
            _RUN_COSTS_USD.append((label, float(cost)))
        cost_str = f", cost=${cost:.4f}" if isinstance(cost, (int, float)) else ""
        sys.stdout.write(f"  ╰─ [{label}] exit {process.returncode}{cost_str}\n\n")
        sys.stdout.flush()

    if timed_out["flag"]:
        return StepOutput(
            content=f'{{"ok": false, "error": "claude -p timed out after {timeout_secs}s"}}'
        )
    if process.returncode != 0:
        tail = _truncate(final_text, 400)
        return StepOutput(
            content=(
                f'{{"ok": false, "error": "claude exit {process.returncode}", '
                f'"stderr_tail": {tail!r}}}'
            )
        )
    return StepOutput(content=final_text)


def make_claude_code_coder_step(
    project_path: str,
    task_content: str,
    *,
    timeout_secs: int = 1800,
    max_budget_usd: Optional[float] = None,
    model_alias: str = "sonnet",
) -> Callable[[StepInput, Optional[Dict[str, Any]]], StepOutput]:
    """Coder step: writes tests + impl + RUN_TESTS.sh through `claude -p`."""
    project = str(Path(project_path).resolve())

    def _claude_code_step(
        step_input: StepInput,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        feedback = step_input.previous_step_content or ""
        return _run_claude_p(
            cwd=project,
            system_prompt=ANDROID_CODER_SYSTEM_PROMPT,
            user_prompt=_build_user_prompt_for_coder(task_content, feedback),
            model_alias=model_alias,
            timeout_secs=timeout_secs,
            max_budget_usd=max_budget_usd,
            label="coder",
        )

    _claude_code_step.__name__ = "claude_code_coder_step"
    return _claude_code_step


def make_claude_code_checker_step(
    project_path: str,
    *,
    timeout_secs: int = 600,
    max_budget_usd: Optional[float] = None,
    model_alias: str = "sonnet",
) -> Callable[[StepInput, Optional[Dict[str, Any]]], StepOutput]:
    """Checker step: runs RUN_TESTS.sh + parses TEST-*.xml through `claude -p`.

    Tools restricted to read+execute (no Edit/Write) — the system prompt forbids
    modifying source, and we enforce it at the CLI level too.
    """
    project = str(Path(project_path).resolve())

    def _claude_code_step(
        step_input: StepInput,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        return _run_claude_p(
            cwd=project,
            system_prompt=CODE_CHECKER_SYSTEM_PROMPT,
            user_prompt=_CHECKER_USER_PROMPT,
            model_alias=model_alias,
            timeout_secs=timeout_secs,
            max_budget_usd=max_budget_usd,
            disallowed_tools=["Edit", "Write"],
            label="checker",
        )

    _claude_code_step.__name__ = "claude_code_checker_step"
    return _claude_code_step

"""Reviewer agent. Read-only tools. Emits a single JSON verdict on the last line."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

import yaml

from claude_agent_sdk import ClaudeAgentOptions, query

from src.project_profile import detect_project_profile
from src.tracker import Tracker


def _get_config() -> dict[str, Any]:
    config_path = Path(os.environ.get("REPO_ROOT", Path.cwd())) / "agent_config.yml"
    if not config_path.exists():
        config_path = Path("agent_config.yml")
    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    if env_impl := os.environ.get("AGENT_IMPLEMENTATION"):
        config["implementation"] = env_impl
    return config or {"implementation": "claude", "agent_timeout": 7200}


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


def _extract_text(message: object) -> str:
    result = getattr(message, "result", None)
    if isinstance(result, str):
        return result
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    return ""


async def _run_gemini(task_id: int, config: dict[str, Any]) -> int:
    gemini_api_key = config.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = gemini_api_key
    agent_timeout = config.get("agent_timeout", 7200)
    gemini_model = config.get("gemini_model", "google/gemini-2.5-flash")
    server_url = config.get("opencode_server_url", "")
    full_prompt = f"{REVIEWER_SYSTEM_PROMPT}\n\n{_build_user_prompt(task_id)}"
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
            print(json.dumps({"approved": False, "notes": f"Reviewer timed out after {agent_timeout}s"}))
            return 1
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            print(f"ERROR: opencode exit {process.returncode}: {stdout[-500:]}", file=sys.stderr)
        lines = [line for line in stdout.splitlines() if line.strip()]
        if lines:
            candidate = lines[-1].strip()
            try:
                parsed = json.loads(candidate)
                print(json.dumps({"approved": bool(parsed["approved"]), "notes": str(parsed.get("notes", ""))}))
                return process.returncode or 0
            except (ValueError, KeyError, TypeError):
                pass
        print(json.dumps({"approved": False, "notes": "Reviewer did not emit valid JSON"}))
        return 1
    except Exception as e:
        print(json.dumps({"approved": False, "notes": str(e)}))
        return 1


async def amain(task_id: int) -> int:
    config = _get_config()
    if config.get("implementation", "claude").lower() == "gemini":
        return await _run_gemini(task_id, config)

    anthropic_api_key = config.get("anthropic_api_key", "")
    if anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = anthropic_api_key

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

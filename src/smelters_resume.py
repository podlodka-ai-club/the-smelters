"""Smelters resume state under ``projects/<Name>/.smelters/resume.json``."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from agno.workflow.types import StepInput, StepOutput

RESUME_SCHEMA_VERSION = 1
RESUME_DIR = ".smelters"
RESUME_FILENAME = "resume.json"


def resume_json_path(project_root: Path | str) -> Path:
    return Path(project_root).resolve() / RESUME_DIR / RESUME_FILENAME


def read_resume_last_checker(path: Path) -> str | None:
    """Return ``last_checker_output`` from a resume file, or None if missing/invalid."""
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    out = data.get("last_checker_output")
    if isinstance(out, str):
        return out
    return None


def write_resume_state(
    path: Path,
    *,
    task_path: Path,
    repo: str,
    max_iterations: int,
    last_checker_output: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": RESUME_SCHEMA_VERSION,
        "task_path": str(task_path.resolve()),
        "repo": repo,
        "max_iterations": max_iterations,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_checker_output": last_checker_output,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def clear_resume_file(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
    try:
        path.parent.rmdir()
    except OSError:
        pass


def merge_resume_into_task_markdown(task_markdown: str, resume_checker_output: str | None) -> str:
    """Prepend prior checker output into the task spec for Agent coders (static instructions)."""
    r = (resume_checker_output or "").strip()
    if not r:
        return task_markdown
    banner = (
        "<!-- smelters-resume: output from the checker on the last failed run; "
        "after the checker runs again, prefer the workflow previous-step checker JSON. -->\n\n"
        f"{r}\n\n"
        "---\n\n"
    )
    return banner + task_markdown


def merge_previous_step_content_for_resume(previous: Any, resume: str) -> str:
    """Combine saved checker output with any existing ``previous_step_content`` (callables)."""
    parts: list[str] = []
    rs = resume.strip()
    if rs:
        parts.append(rs)
    prev_s = "" if previous is None else (previous if isinstance(previous, str) else str(previous))
    if prev_s.strip():
        parts.append(prev_s.strip())
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[0] + "\n\n--- (prior workflow context) ---\n\n" + parts[1]


def wrap_callable_coder_for_resume(
    coder_step: Callable[..., StepOutput],
    resume_checker_output: str | None,
) -> Callable[..., StepOutput]:
    """Seed iteration 1 only: synthetic ``previous_step_content`` from last checker (opencode / claude-cli)."""
    if not (resume_checker_output or "").strip():
        return coder_step
    rf = resume_checker_output.strip()
    seeded = False

    def _wrapped(
        step_input: StepInput,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        nonlocal seeded
        si = step_input
        if not seeded:
            seeded = True
            merged = merge_previous_step_content_for_resume(step_input.previous_step_content, rf)
            si = replace(step_input, previous_step_content=merged or rf)
        if session_state is None:
            return coder_step(si)
        return coder_step(si, session_state)

    _wrapped.__name__ = getattr(coder_step, "__name__", "coder_step") + "_with_resume"
    return _wrapped

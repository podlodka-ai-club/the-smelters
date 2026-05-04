from __future__ import annotations

import json
from pathlib import Path

from agno.workflow.types import StepInput, StepOutput

from src.smelters_resume import (
    merge_resume_into_task_markdown,
    read_resume_last_checker,
    resume_json_path,
    wrap_callable_coder_for_resume,
    write_resume_state,
)


def test_wrap_callable_seeds_only_first_invocation() -> None:
    seen: list[str | None] = []

    def inner(step_input: StepInput, session_state=None) -> StepOutput:
        prev = step_input.previous_step_content
        seen.append(prev if isinstance(prev, str) else None)
        return StepOutput(content="ok")

    wrapped = wrap_callable_coder_for_resume(inner, '{"status":"failed"}')
    wrapped(StepInput(previous_step_content=None), None)
    wrapped(StepInput(previous_step_content="checker-round-2"), None)
    assert seen[0] is not None and '{"status":"failed"}' in seen[0]
    assert seen[1] == "checker-round-2"


def test_merge_resume_prepends_banner(tmp_path: Path) -> None:
    task = "Project: X\nbody"
    out = merge_resume_into_task_markdown(task, '{"status":"failed"}')
    assert "Project: X" in out
    assert '{"status":"failed"}' in out
    assert out.startswith("<!-- smelters-resume")


def test_write_and_read_resume_roundtrip(tmp_path: Path) -> None:
    p = resume_json_path(tmp_path)
    write_resume_state(
        p,
        task_path=tmp_path / "t.md",
        repo="o/r",
        max_iterations=3,
        last_checker_output='{"status":"failed"}',
    )
    assert p.is_file()
    body = json.loads(p.read_text(encoding="utf-8"))
    assert body["repo"] == "o/r"
    assert read_resume_last_checker(p) == '{"status":"failed"}'

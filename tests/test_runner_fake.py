from __future__ import annotations

import json
import os

import pytest

from agents.runner import run_agent
from src.models import Task


def _task(task_id: int = 1, worktree: str = ".") -> Task:
    return Task(
        id=task_id,
        task_number=task_id,
        title=f"task {task_id}",
        spec_path=f"tasks/python_fixture/{task_id}.md",
        status="running",
        attempts=0,
        worktree=worktree,
        branch=f"task-{task_id}",
        review_notes=None,
    )


@pytest.mark.asyncio
async def test_runner_reads_final_json_from_fake_coder(tmp_events) -> None:
    os.environ["FAKE_CODER"] = "ok"
    result = await run_agent(role="fake_coder", task=_task(), events_path=tmp_events, timeout=10)
    assert result.exit_code == 0
    payload = json.loads(result.stdout_final)
    assert payload["ok"] is True


@pytest.mark.asyncio
async def test_runner_surfaces_nonzero_exit(tmp_events) -> None:
    os.environ["FAKE_CODER"] = "crash"
    result = await run_agent(role="fake_coder", task=_task(), events_path=tmp_events, timeout=10)
    assert result.exit_code == 1
    assert result.error is not None


@pytest.mark.asyncio
async def test_runner_enforces_timeout(tmp_events) -> None:
    os.environ["FAKE_CODER"] = "timeout"
    result = await run_agent(role="fake_coder", task=_task(), events_path=tmp_events, timeout=1)
    assert result.exit_code != 0
    assert "timeout" in (result.error or "").lower()

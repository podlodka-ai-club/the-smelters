from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from orchestrator import Orchestrator
from src.tracker import Tracker


@pytest.fixture
def seeded(tmp_path: Path, tmp_db: Path, tmp_events: Path) -> dict[str, object]:
    projects_root = tmp_path / "projects"
    target = projects_root / "python_fixture"
    target.mkdir(parents=True)
    subprocess.run(["git", "-C", str(target), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(target), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(target), "config", "user.name", "t"], check=True)
    (target / "a.txt").write_text("hello\n")
    subprocess.run(["git", "-C", str(target), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(target), "-c", "commit.gpgsign=false", "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    tracker = Tracker(tmp_db)
    tracker.init_schema()
    task_id = tracker.insert_task(
        title="fake task",
        project="python_fixture",
        spec_path="tasks/fake.md",
    )
    return {
        "tracker": tracker,
        "task_id": task_id,
        "projects_root": projects_root,
        "tasks_root": tmp_path / "tasks",
        "events": tmp_events,
        "worktrees": tmp_path / "wt",
    }


@pytest.mark.asyncio
async def test_happy_path_closes_task(seeded, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "approve")
    orch = Orchestrator(
        tracker=seeded["tracker"],
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="fake_coder",
        reviewer_role="fake_reviewer",
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )
    await orch.run_until_empty()
    assert seeded["tracker"].get_task(seeded["task_id"]).status == "closed"


@pytest.mark.asyncio
async def test_reject_then_approve_loops(seeded, monkeypatch) -> None:
    task_id = seeded["task_id"]
    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "reject_then_approve")
    orch = Orchestrator(
        tracker=seeded["tracker"],
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="fake_coder",
        reviewer_role="fake_reviewer",
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )
    await orch.run_until_empty()
    row = seeded["tracker"].get_task(task_id)
    assert row.status == "closed"
    assert row.attempts >= 1


@pytest.mark.asyncio
async def test_always_rejected_fails_after_max_attempts(seeded, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "reject")
    orch = Orchestrator(
        tracker=seeded["tracker"],
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="fake_coder",
        reviewer_role="fake_reviewer",
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )
    await orch.run_until_empty()
    row = seeded["tracker"].get_task(seeded["task_id"])
    assert row.status == "failed"
    assert row.attempts == 3


@pytest.mark.asyncio
async def test_coder_crash_counts_as_attempt(seeded, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_CODER", "crash")
    monkeypatch.setenv("FAKE_REVIEWER", "approve")
    orch = Orchestrator(
        tracker=seeded["tracker"],
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="fake_coder",
        reviewer_role="fake_reviewer",
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )
    await orch.run_until_empty()
    row = seeded["tracker"].get_task(seeded["task_id"])
    assert row.status == "failed"
    assert row.attempts == 3


@pytest.mark.asyncio
async def test_malformed_reviewer_treated_as_rejection(seeded, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "malformed")
    orch = Orchestrator(
        tracker=seeded["tracker"],
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="fake_coder",
        reviewer_role="fake_reviewer",
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )
    await orch.run_until_empty()
    row = seeded["tracker"].get_task(seeded["task_id"])
    assert row.status == "failed"

from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator import Orchestrator, main
from src.tracker import Tracker


@pytest.fixture
def seeded(tmp_path: Path, tmp_db: Path, tmp_events: Path) -> dict[str, object]:
    projects_root = tmp_path / "projects"
    target = projects_root / "python_fixture"
    target.mkdir(parents=True)
    (target / "a.txt").write_text("hello\n")

    tracker = Tracker(tmp_db)
    tracker.init_schema()
    row_id = tracker.insert_task(
        task_number=1,
        title="fake task",
        spec_path="tasks/python_fixture/1-fake.md",
    )
    return {
        "tracker": tracker,
        "task_id": row_id,
        "projects_root": projects_root,
        "tasks_root": tmp_path / "tasks",
        "events": tmp_events,
        "worktrees": tmp_path / "wt",
    }


def test_main_requires_project() -> None:
    with pytest.raises(SystemExit):
        main([])


@pytest.mark.asyncio
async def test_happy_path_closes_task(seeded, monkeypatch) -> None:
    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "approve")
    orch = Orchestrator(
        tracker=seeded["tracker"],
        project="python_fixture",
        root_path=seeded["tasks_root"].parent,
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
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
        project="python_fixture",
        root_path=seeded["tasks_root"].parent,
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
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
        project="python_fixture",
        root_path=seeded["tasks_root"].parent,
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
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
        project="python_fixture",
        root_path=seeded["tasks_root"].parent,
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
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
        project="python_fixture",
        root_path=seeded["tasks_root"].parent,
        events_path=seeded["events"],
        projects_root=seeded["projects_root"],
        tasks_root=seeded["tasks_root"],
        worktrees_root=seeded["worktrees"],
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )
    await orch.run_until_empty()
    row = seeded["tracker"].get_task(seeded["task_id"])
    assert row.status == "failed"


@pytest.mark.asyncio
async def test_task_filter_processes_only_selected_task_number(tmp_path: Path, tmp_db: Path, tmp_events: Path, monkeypatch) -> None:
    projects_root = tmp_path / "projects"
    project_repo = projects_root / "DemoApp"
    project_repo.mkdir(parents=True)
    (project_repo / "demo.txt").write_text("demo\n")

    tracker = Tracker(tmp_db)
    tracker.init_schema()
    first_task = tracker.insert_task(task_number=7, title="first task", spec_path="tasks/DemoApp/7-first.md")
    second_task = tracker.insert_task(task_number=9, title="second task", spec_path="tasks/DemoApp/9-second.md")

    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "approve")
    orch = Orchestrator(
        tracker=tracker,
        project="DemoApp",
        root_path=tmp_path,
        events_path=tmp_events,
        projects_root=projects_root,
        tasks_root=tmp_path / "tasks",
        worktrees_root=tmp_path / "wt",
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
        task_filter=9,
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )

    await orch.run_until_empty()

    assert tracker.get_task(first_task).status == "ready"
    assert tracker.get_task(second_task).status == "closed"


@pytest.mark.asyncio
async def test_task_filter_ignores_row_id_and_matches_task_number(tmp_path: Path, tmp_db: Path, tmp_events: Path, monkeypatch) -> None:
    projects_root = tmp_path / "projects"
    project_repo = projects_root / "DemoApp"
    project_repo.mkdir(parents=True)
    (project_repo / "demo.txt").write_text("demo\n")

    tracker = Tracker(tmp_db)
    tracker.init_schema()
    first_row_id = tracker.insert_task(task_number=7, title="task seven", spec_path="tasks/DemoApp/7-seven.md")
    second_row_id = tracker.insert_task(task_number=2, title="task two", spec_path="tasks/DemoApp/2-two.md")

    monkeypatch.setenv("FAKE_CODER", "ok")
    monkeypatch.setenv("FAKE_REVIEWER", "approve")
    orch = Orchestrator(
        tracker=tracker,
        project="DemoApp",
        root_path=tmp_path,
        events_path=tmp_events,
        projects_root=projects_root,
        tasks_root=tmp_path / "tasks",
        worktrees_root=tmp_path / "wt",
        coder_role="tests.fixtures.fake_coder",
        reviewer_role="tests.fixtures.fake_reviewer",
        task_filter=2,
        max_attempts=3,
        coder_timeout=10,
        reviewer_timeout=10,
    )

    await orch.run_until_empty()

    assert tracker.get_task(first_row_id).status == "ready"
    assert tracker.get_task(second_row_id).status == "closed"

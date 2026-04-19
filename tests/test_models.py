from __future__ import annotations

from dataclasses import fields

from src.models import AgentResult, Task


def test_task_and_agent_result_expose_expected_fields() -> None:
    task_field_names = [field.name for field in fields(Task)]
    result_field_names = [field.name for field in fields(AgentResult)]

    assert task_field_names == [
        "id",
        "task_number",
        "title",
        "spec_path",
        "status",
        "attempts",
        "worktree",
        "branch",
        "review_notes",
    ]
    assert result_field_names == ["exit_code", "stdout_final", "error"]


def test_task_and_agent_result_store_values() -> None:
    task = Task(
        id=1,
        task_number=7,
        title="Fix bug",
        spec_path="tasks/python_fixture/7-fix-bug.md",
        status="ready",
        attempts=0,
        worktree=None,
        branch=None,
        review_notes=None,
    )
    result = AgentResult(exit_code=0, stdout_final="ok")

    assert task.status == "ready"
    assert task.task_number == 7
    assert task.spec_path.endswith(".md")
    assert result.exit_code == 0
    assert result.stdout_final == "ok"
    assert result.error is None

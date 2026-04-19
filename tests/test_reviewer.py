from __future__ import annotations

import pytest

from agents import reviewer


@pytest.mark.asyncio
async def test_amain_uses_noninteractive_permission_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr(reviewer, "_build_user_prompt", lambda task_id: f"review:{task_id}")

    async def fake_query(*, prompt, options):  # type: ignore[no-untyped-def]
        assert prompt == "review:11"
        assert options.permission_mode == "dontAsk"

        class Message:
            result = '{"approved": true, "notes": "ok"}'

        yield Message()

    monkeypatch.setattr(reviewer, "query", fake_query)

    assert await reviewer.amain(11) == 0
    assert capsys.readouterr().out.strip() == '{"approved": true, "notes": "ok"}'


def test_build_user_prompt_mentions_committed_and_working_tree_diffs(monkeypatch) -> None:
    monkeypatch.setattr(
        reviewer,
        "_load_task",
        lambda task_id: (task_id, f"title-{task_id}", "tasks/001.md", "spec body"),
    )
    monkeypatch.setattr(
        reviewer,
        "detect_project_profile",
        lambda cwd: type(
            "Profile",
            (),
            {
                "label": "python",
                "reviewer_verification": "pytest",
                "default_test_command": "pytest",
            },
        )(),
    )

    prompt = reviewer._build_user_prompt(1)

    assert "git diff main...HEAD" in prompt
    assert "git diff" in prompt
    assert "git status --short" in prompt
    assert "Accept either a committed fix or a correct uncommitted working-tree fix." in prompt

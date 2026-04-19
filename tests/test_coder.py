from __future__ import annotations

from collections.abc import AsyncIterable

import pytest

from agents import coder


@pytest.mark.asyncio
async def test_amain_uses_streaming_prompt_for_query(monkeypatch) -> None:
    monkeypatch.setattr(coder, "_build_user_prompt", lambda task_id: f"task:{task_id}")

    async def fake_query(*, prompt, options):  # type: ignore[no-untyped-def]
        assert isinstance(prompt, AsyncIterable)
        messages = []
        async for item in prompt:
            messages.append(item)
        assert messages == [
            {
                "type": "user",
                "message": {"role": "user", "content": "task:7"},
                "parent_tool_use_id": None,
                "session_id": "default",
            }
        ]

        class Message:
            result = '{"ok": true, "summary": "done"}'

        yield Message()

    monkeypatch.setattr(coder, "query", fake_query)

    assert await coder.amain(7) == 0

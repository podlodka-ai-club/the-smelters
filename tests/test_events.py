from __future__ import annotations

import json
from pathlib import Path

from src.events import emit_event, read_events


def test_emit_event_appends_jsonl_line(tmp_events: Path) -> None:
    emit_event(tmp_events, task_id=1, actor="orchestrator", type="task_claimed", attempt=1)
    lines = tmp_events.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["task_id"] == 1
    assert row["actor"] == "orchestrator"
    assert row["type"] == "task_claimed"
    assert row["attempt"] == 1
    assert row["ts"].endswith("Z")


def test_emit_event_accepts_null_task_id(tmp_events: Path) -> None:
    emit_event(tmp_events, task_id=None, actor="orchestrator", type="startup")
    row = json.loads(tmp_events.read_text().splitlines()[0])
    assert row["task_id"] is None


def test_read_events_yields_in_order(tmp_events: Path) -> None:
    emit_event(tmp_events, task_id=1, actor="orchestrator", type="task_claimed")
    emit_event(tmp_events, task_id=1, actor="coder", type="agent_started", pid=99)
    rows = list(read_events(tmp_events))
    assert [row["type"] for row in rows] == ["task_claimed", "agent_started"]
    assert rows[1]["pid"] == 99


def test_emit_event_is_atomic_per_line(tmp_events: Path) -> None:
    emit_event(tmp_events, task_id=1, actor="coder", type="tool_use", text="line1\nline2")
    lines = tmp_events.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["text"] == "line1\nline2"

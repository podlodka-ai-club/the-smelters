from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit_event(
    events_path: Path,
    *,
    task_id: int | None,
    actor: str,
    type: str,
    **fields: Any,
) -> None:
    record = {
        "ts": _now_iso(),
        "task_id": task_id,
        "actor": actor,
        "type": type,
        **fields,
    }
    line = json.dumps(record, ensure_ascii=False)
    with events_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(f"{line}\n")


def read_events(events_path: Path) -> Iterator[dict[str, Any]]:
    if not events_path.exists():
        return

    with events_path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.rstrip("\n")
            if not line:
                continue
            yield json.loads(line)

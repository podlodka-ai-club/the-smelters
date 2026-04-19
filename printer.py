"""Minimal tail of events.jsonl with color-coded lines. No deps beyond stdlib."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from src.runtime_paths import project_runtime_paths


COLORS = {
    "orchestrator": "\033[36m",
    "coder": "\033[33m",
    "reviewer": "\033[35m",
    "tui": "\033[37m",
}
RESET = "\033[0m"


def _fmt(event: dict) -> str:
    actor = event.get("actor", "?")
    color = COLORS.get(actor, "")
    task_id = event.get("task_id")
    ts = event.get("ts", "")
    event_type = event.get("type", "")
    extras = {
        key: value
        for key, value in event.items()
        if key not in ("ts", "actor", "task_id", "type")
    }
    extras_str = " ".join(
        f"{key}={json.dumps(value) if not isinstance(value, str) else value}"
        for key, value in extras.items()
    )
    return f"{color}{ts} task={task_id} {actor:>12} {event_type}{RESET}  {extras_str}"


def follow(path: Path) -> None:
    if path.exists():
        with path.open("r", encoding="utf-8") as file_obj:
            for line in file_obj:
                line = line.strip()
                if line:
                    print(_fmt(json.loads(line)))
        file_pos = path.stat().st_size
    else:
        file_pos = 0

    while True:
        if not path.exists():
            time.sleep(0.2)
            continue
        size = path.stat().st_size
        if size > file_pos:
            with path.open("r", encoding="utf-8") as file_obj:
                file_obj.seek(file_pos)
                for line in file_obj:
                    line = line.strip()
                    if line:
                        print(_fmt(json.loads(line)))
                file_pos = file_obj.tell()
        time.sleep(0.1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)
    runtime = project_runtime_paths(args.root.resolve(), args.project)
    try:
        follow(runtime.events_path)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

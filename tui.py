"""Textual dashboard. Left: task table. Right: event timeline for the selected task."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog

from src.runtime_paths import project_runtime_paths


def load_task_rows(db_path: Path) -> list[tuple[str, str, str, str]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = list(conn.execute("SELECT task_number, status, attempts, title FROM tasks ORDER BY task_number"))
    finally:
        conn.close()
    return [
        (str(row["task_number"]), row["status"], str(row["attempts"]), row["title"])
        for row in rows
    ]


class Dashboard(App):
    CSS = """
    #tasks { width: 40%; }
    #timeline { width: 60%; }
    """

    def __init__(self, *, db_path: Path, events_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.events_path = events_path
        self._events_pos = 0
        self._events: list[dict] = []
        self._selected_task: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="tasks"):
                yield DataTable(id="tasks_table")
            with Vertical(id="timeline"):
                yield RichLog(id="log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tasks_table", DataTable)
        table.add_columns("task", "status", "attempts", "title")
        table.cursor_type = "row"
        self.set_interval(0.5, self._refresh_tasks)
        self.set_interval(0.2, self._pull_events)

    def _refresh_tasks(self) -> None:
        table = self.query_one("#tasks_table", DataTable)
        table.clear()
        try:
            rows = load_task_rows(self.db_path)
        except sqlite3.OperationalError:
            return
        for row in rows:
            table.add_row(
                *row,
                key=row[0],
            )

    def _pull_events(self) -> None:
        if not self.events_path.exists():
            return

        size = self.events_path.stat().st_size
        if size <= self._events_pos:
            return

        with self.events_path.open("r", encoding="utf-8") as file_obj:
            file_obj.seek(self._events_pos)
            for line in file_obj:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self._events_pos = file_obj.tell()

        self._rerender_log()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            self._selected_task = int(event.row_key.value)
        except (TypeError, ValueError, AttributeError):
            self._selected_task = None
        self._rerender_log()

    def _rerender_log(self) -> None:
        log = self.query_one("#log", RichLog)
        log.clear()
        if self._selected_task is None:
            relevant = self._events
        else:
            relevant = [event for event in self._events if event.get("task_id") == self._selected_task]

        for event in relevant[-500:]:
            color = {
                "orchestrator": "cyan",
                "coder": "yellow",
                "reviewer": "magenta",
            }.get(event.get("actor", ""), "white")
            extras = {
                key: value
                for key, value in event.items()
                if key not in ("ts", "actor", "type", "task_id")
            }
            log.write(
                f"[{color}]{event.get('ts', '')} {event.get('actor', ''):>12} "
                f"{event.get('type', '')}[/{color}]  {json.dumps(extras)}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)
    runtime = project_runtime_paths(args.root.resolve(), args.project)
    Dashboard(db_path=runtime.db_path, events_path=runtime.events_path).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

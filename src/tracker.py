from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator

from src.models import Status, Task


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id           INTEGER PRIMARY KEY,
  task_number  INTEGER NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  spec_path    TEXT NOT NULL,
  status       TEXT NOT NULL,
  attempts     INTEGER NOT NULL DEFAULT 0,
  worktree     TEXT,
  branch       TEXT,
  review_notes TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status ON tasks(status);
"""


class TaskNotFound(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        task_number=row["task_number"],
        title=row["title"],
        spec_path=row["spec_path"],
        status=row["status"],
        attempts=row["attempts"],
        worktree=row["worktree"],
        branch=row["branch"],
        review_notes=row["review_notes"],
    )


class Tracker:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def insert_task(self, *, task_number: int, title: str, spec_path: str) -> int:
        now = _now()
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (task_number, title, spec_path, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'ready', ?, ?)",
                (task_number, title, spec_path, now, now),
            )
            return int(cursor.lastrowid)

    def get_task(self, task_id: int) -> Task:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            return _row_to_task(row)

    def list_tasks(self) -> Iterator[Task]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY task_number").fetchall()

        for row in rows:
            yield _row_to_task(row)

    def claim_next_ready_task(
        self,
        *,
        project: str | None = None,
        task_id: int | None = None,
    ) -> Task | None:
        now = _now()
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            query = "SELECT * FROM tasks WHERE status='ready'"
            params: list[object] = []
            if project is not None:
                query += " AND spec_path LIKE ?"
                params.append(f"tasks/{project}/%")
            if task_id is not None:
                query += " AND task_number=?"
                params.append(task_id)
            query += " ORDER BY task_number LIMIT 1"
            row = conn.execute(query, tuple(params)).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                "UPDATE tasks SET status='running', updated_at=? WHERE id=?",
                (now, row["id"]),
            )
            conn.execute("COMMIT")
            updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (row["id"],)).fetchone()
            assert updated is not None
            return _row_to_task(updated)

    def set_status(self, task_id: int, status: Status) -> None:
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                (status, _now(), task_id),
            )
            if cursor.rowcount == 0:
                raise TaskNotFound(task_id)

    def increment_attempts(self, task_id: int) -> None:
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET attempts = attempts + 1, updated_at=? WHERE id=?",
                (_now(), task_id),
            )
            if cursor.rowcount == 0:
                raise TaskNotFound(task_id)

    def save_review_notes(self, task_id: int, notes: str) -> None:
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET review_notes=?, updated_at=? WHERE id=?",
                (notes, _now(), task_id),
            )
            if cursor.rowcount == 0:
                raise TaskNotFound(task_id)

    def set_worktree(self, task_id: int, *, worktree: str, branch: str) -> None:
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET worktree=?, branch=?, updated_at=? WHERE id=?",
                (worktree, branch, _now(), task_id),
            )
            if cursor.rowcount == 0:
                raise TaskNotFound(task_id)

    def reset_stuck_tasks(self) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE tasks SET status='ready', updated_at=? "
                "WHERE status IN ('running', 'review')",
                (_now(),),
            )

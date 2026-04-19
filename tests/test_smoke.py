from __future__ import annotations

from pathlib import Path


def test_tmp_fixtures_return_expected_paths(
    tmp_db: Path,
    tmp_events: Path,
    tmp_target_repo: Path,
) -> None:
    assert tmp_db.name == "tasks.db"
    assert tmp_events.name == "events.jsonl"
    assert tmp_target_repo.name == "target_repo"
    assert tmp_target_repo.exists()

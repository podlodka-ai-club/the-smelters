from __future__ import annotations

import json

from shared.checker_utils import (
    extract_and_validate_json,
    last_json_line_with_checker_status,
    normalize_checker_stdout_to_json_content,
)


def test_last_json_line_prefers_last_contract_line() -> None:
    text = "noise\n{\"status\": \"failed\"}\n{\"status\": \"passed\", \"failed_tests\": []}\n"
    line = last_json_line_with_checker_status(text)
    assert line is not None
    assert json.loads(line)["status"] == "passed"


def test_last_json_line_ignores_non_object_or_missing_status() -> None:
    assert last_json_line_with_checker_status("[1,2]") is None
    assert last_json_line_with_checker_status('{"no_status": true}') is None


def test_normalize_checker_stdout_contract_ok() -> None:
    raw = "log\n{\"status\": \"passed\", \"failed_tests\": [], \"build_errors\": \"\"}\n"
    out = json.loads(normalize_checker_stdout_to_json_content(raw))
    assert out["status"] == "passed"


def test_normalize_checker_stdout_exit_zero_shape_without_contract() -> None:
    raw = "opencode finished\nno json here\n"
    out = json.loads(normalize_checker_stdout_to_json_content(raw))
    assert out["status"] == "failed"
    assert "subprocess exit code 0" in (out.get("build_errors") or "")


def test_extract_and_validate_json_rejects_bad_status_value() -> None:
    out = extract_and_validate_json('{"status": "maybe", "failed_tests": []}')
    assert out["status"] == "failed"

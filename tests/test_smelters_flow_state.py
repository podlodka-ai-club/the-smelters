from __future__ import annotations

from src.smelters_flow_state import checker_passed_from_content, pr_created_from_state


def test_checker_passed_from_content_detects_passed_status() -> None:
    content = 'log line\n{"status":"passed","failed_tests":[]}\n'
    assert checker_passed_from_content(content) is True


def test_checker_passed_from_content_detects_failure_status() -> None:
    content = '{"status":"failed","failed_tests":[{"name":"x"}]}'
    assert checker_passed_from_content(content) is False


def test_pr_created_from_state_true_when_ok_flag_present() -> None:
    assert pr_created_from_state({"pr_create_result": {"ok": True}}) is True


def test_pr_created_from_state_false_when_missing() -> None:
    assert pr_created_from_state({}) is False

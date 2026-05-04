from __future__ import annotations

from src.smelters_flow_state import (
    checker_infrastructure_error_from_content,
    checker_passed_from_content,
    pr_created_from_state,
)


def test_checker_passed_from_content_detects_passed_status() -> None:
    content = 'log line\n{"status":"passed","failed_tests":[]}\n'
    assert checker_passed_from_content(content) is True


def test_checker_passed_from_content_detects_failure_status() -> None:
    content = '{"status":"failed","failed_tests":[{"name":"x"}]}'
    assert checker_passed_from_content(content) is False


def test_checker_infrastructure_error_from_content_true() -> None:
    raw = 'log\n{"status":"error","scope":"checker","message":"x","detail":"y"}\n'
    assert checker_infrastructure_error_from_content(raw) is True


def test_checker_infrastructure_error_from_content_wrong_scope() -> None:
    raw = '{"status":"error","scope":"other","message":"x"}'
    assert checker_infrastructure_error_from_content(raw) is False


def test_checker_infrastructure_error_from_content_failed_status() -> None:
    assert checker_infrastructure_error_from_content('{"status":"failed"}') is False


def test_pr_created_from_state_true_when_ok_flag_present() -> None:
    assert pr_created_from_state({"pr_create_result": {"ok": True}}) is True


def test_pr_created_from_state_false_when_missing() -> None:
    assert pr_created_from_state({}) is False

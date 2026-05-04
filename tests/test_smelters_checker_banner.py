from __future__ import annotations

from io import StringIO
from pathlib import Path

from src.smelters_checker_banner import (
    CheckerGateFailureKind,
    checker_failure_hint_one_line,
    classify_last_checker_raw,
)
from src.smelters_flow_failure import print_smelters_flow_failed_banner


def test_classify_empty() -> None:
    assert classify_last_checker_raw(None) == CheckerGateFailureKind.EMPTY
    assert classify_last_checker_raw("   ") == CheckerGateFailureKind.EMPTY


def test_classify_no_valid_contract() -> None:
    assert classify_last_checker_raw("just prose\nno json") == CheckerGateFailureKind.NO_VALID_CONTRACT
    assert classify_last_checker_raw('{"no_status": true}') == CheckerGateFailureKind.NO_VALID_CONTRACT


def test_classify_contract_failed() -> None:
    raw = 'log\n{"status": "failed", "failed_tests": [], "build_errors": "compile error"}\n'
    assert classify_last_checker_raw(raw) == CheckerGateFailureKind.CONTRACT_FAILED


def test_classify_passed_unexpected() -> None:
    raw = '{"status": "passed", "failed_tests": []}\n'
    assert classify_last_checker_raw(raw) == CheckerGateFailureKind.PASSED_UNEXPECTED


def test_checker_failure_hint_prefers_failed_tests() -> None:
    raw = '{"status": "failed", "failed_tests": [{"name": "FooTest"}], "build_errors": ""}'
    hint = checker_failure_hint_one_line(raw)
    assert hint is not None
    assert "FooTest" in hint
    assert "1 failing" in hint


def test_checker_failure_hint_build_errors() -> None:
    raw = '{"status": "failed", "failed_tests": [], "build_errors": "e: file.kt:1:1 oops"}'
    hint = checker_failure_hint_one_line(raw)
    assert hint is not None
    assert "oops" in hint


def test_banner_contract_failed_does_not_blame_missing_json_contract() -> None:
    buf = StringIO()
    last = '{"status": "failed", "failed_tests": [{"name": "T"}], "build_errors": ""}'
    print_smelters_flow_failed_banner(
        resume_file=Path("/tmp/.smelters/resume.json"),
        suggested_command="uv run python agno_orchestrator.py --resume",
        coder_loop_total_iterations=3,
        coder_loop_max_iterations=3,
        last_checker_raw=last,
        file=buf,
    )
    out = buf.getvalue()
    assert "valid JSON contract" in out and "failed" in out
    assert "did not contain an accepted JSON line" not in out
    assert "1 failing test(s)" in out
    assert "first: T" in out


def test_banner_no_contract_keeps_gate_wording() -> None:
    buf = StringIO()
    print_smelters_flow_failed_banner(
        resume_file=Path("/tmp/r.json"),
        suggested_command="uv run x",
        coder_loop_total_iterations=2,
        coder_loop_max_iterations=3,
        last_checker_raw="model said done\nno json line\n",
        file=buf,
    )
    out = buf.getvalue()
    assert "did not contain an accepted JSON line" in out
    assert "subprocess exit code 0" in out

from __future__ import annotations

from unittest.mock import MagicMock

from agno.workflow.types import StepInput, StepOutput

from agno_orchestrator import (
    _checker_passed_from_step,
    _coder_checker_loop_finished,
)


def test_pr_gate_reads_passed_from_nested_loop_steps() -> None:
    passed = '{"status":"passed","failed_tests":[],"build_errors":"","timeout":false,"flaky":false}'
    loop_inner = [
        StepOutput(step_name="opencode_coder_step", content="code"),
        StepOutput(step_name="opencode_checker_step", content=passed),
        StepOutput(step_name="diff_tracker", content=passed),
    ]
    loop_out = StepOutput(step_name="CoderCheckerLoop", content="Loop CoderCheckerLoop completed 1 iterations", steps=loop_inner)
    si = StepInput(
        previous_step_content=loop_out.content,
        previous_step_outputs={"CoderCheckerLoop": loop_out},
    )
    assert _checker_passed_from_step(si, None) is True


def test_pr_gate_false_when_loop_has_only_failed() -> None:
    failed = '{"status":"failed","failed_tests":[],"build_errors":"e"}'
    loop_inner = [
        StepOutput(content="c"),
        StepOutput(content=failed),
        StepOutput(content=failed),
    ]
    loop_out = StepOutput(step_name="CoderCheckerLoop", content="Loop summary", steps=loop_inner)
    si = StepInput(
        previous_step_content=loop_out.content,
        previous_step_outputs={"CoderCheckerLoop": loop_out},
    )
    assert _checker_passed_from_step(si, None) is False


def test_coder_checker_loop_finished_on_infra_error() -> None:
    infra = '{"status":"error","scope":"checker","message":"timeout","detail":""}'
    outputs = [
        MagicMock(content="c"),
        MagicMock(content=infra),
        MagicMock(content=infra),
    ]
    assert _coder_checker_loop_finished(outputs) is True


def test_coder_checker_loop_not_finished_on_failed_tests() -> None:
    failed = '{"status":"failed","failed_tests":[],"build_errors":"tests"}'
    outputs = [
        MagicMock(content="c"),
        MagicMock(content=failed),
        MagicMock(content=failed),
    ]
    assert _coder_checker_loop_finished(outputs) is False

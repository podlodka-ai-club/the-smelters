from __future__ import annotations

from unittest.mock import MagicMock

from agno.run.base import RunStatus
from agno.run.workflow import LoopExecutionCompletedEvent, LoopIterationCompletedEvent
from agno.workflow.types import StepOutput

from src.smelters_post_run import summarize_smelters_post_run


def test_summarize_prefers_last_checker_iteration_output() -> None:
    wf = MagicMock()
    wf.get_session_state.return_value = {}

    ev1 = LoopIterationCompletedEvent(
        iteration_results=[StepOutput(content="c1"), StepOutput(content='{"status":"failed"}')],
    )
    ev2 = LoopIterationCompletedEvent(
        iteration_results=[StepOutput(content="c2"), StepOutput(content='{"status":"failed","x":2}')],
    )
    run = MagicMock()
    run.events = [ev1, ev2]
    run.status = RunStatus.completed
    wf.get_last_run_output.return_value = run

    s = summarize_smelters_post_run(wf, "sid")
    assert s.last_checker_raw == '{"status":"failed","x":2}'
    assert s.pr_create_step_ran is False


def test_summarize_detects_pr_create_in_session() -> None:
    wf = MagicMock()
    wf.get_session_state.return_value = {"pr_create_result": {"ok": True, "pr_number": 1}}
    run = MagicMock()
    run.events = []
    run.status = RunStatus.completed
    wf.get_last_run_output.return_value = run

    s = summarize_smelters_post_run(wf, "sid")
    assert s.pr_create_step_ran is True
    assert s.pr_create_ok is True


def test_loop_stats_from_named_loop() -> None:
    wf = MagicMock()
    wf.get_session_state.return_value = {}
    ev = LoopExecutionCompletedEvent(
        step_name="CoderCheckerLoop",
        total_iterations=3,
        max_iterations=3,
    )
    run = MagicMock()
    run.events = [ev]
    run.status = RunStatus.completed
    wf.get_last_run_output.return_value = run

    s = summarize_smelters_post_run(wf, "sid")
    assert s.coder_loop_total_iterations == 3
    assert s.coder_loop_max_iterations == 3

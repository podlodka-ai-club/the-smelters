"""Stderr messaging when Smelters ends without opening the PR path."""

from __future__ import annotations

import shlex
import sys
from argparse import Namespace
from pathlib import Path

from src.smelters_checker_banner import (
    CheckerGateFailureKind,
    checker_failure_hint_one_line,
    classify_last_checker_raw,
)


def build_smelters_rerun_cli_command(
    args: Namespace,
    *,
    task_path: Path,
    project_path: Path,
    agent_config_file: Path | None,
    repo: str,
    base_branch: str,
    suggested_max_iterations: int,
    include_resume_flag: bool,
) -> str:
    """Build a copy-paste ``uv run python agno_orchestrator.py …`` line with a higher iteration budget."""
    parts: list[str] = [
        "uv",
        "run",
        "python",
        "agno_orchestrator.py",
        "--task",
        str(task_path),
        "--project",
        str(project_path),
        "--repo",
        repo,
        "--base-branch",
        base_branch,
        "--max-iterations",
        str(suggested_max_iterations),
        "--github-token-env",
        getattr(args, "github_token_env", "GITHUB_TOKEN"),
        "--task-context-mode",
        getattr(args, "task_context_mode", "inline"),
    ]
    if agent_config_file is not None:
        parts.extend(["--agent-config", str(agent_config_file)])
    if getattr(args, "coder", None):
        parts.extend(["--coder", str(args.coder)])
    if getattr(args, "checker", None):
        parts.extend(["--checker", str(args.checker)])
    if getattr(args, "reviewer", None):
        parts.extend(["--reviewer", str(args.reviewer)])
    if getattr(args, "coder_model", None):
        parts.extend(["--coder-model", str(args.coder_model)])
    if getattr(args, "checker_model", None):
        parts.extend(["--checker-model", str(args.checker_model)])
    if getattr(args, "head_branch", None):
        parts.extend(["--head-branch", str(args.head_branch)])
    if getattr(args, "pr_title", None):
        parts.extend(["--pr-title", str(args.pr_title)])
    if getattr(args, "pr_body_file", None):
        parts.extend(["--pr-body-file", str(args.pr_body_file)])
    if getattr(args, "debug_logging", False):
        parts.append("--debug-logging")
    if include_resume_flag:
        parts.append("--resume")
    return " ".join(shlex.quote(p) for p in parts)


def print_smelters_flow_failed_banner(
    *,
    resume_file: Path,
    suggested_command: str,
    coder_loop_total_iterations: int | None,
    coder_loop_max_iterations: int | None,
    last_checker_raw: str | None = None,
    file=sys.stderr,
) -> None:
    kind = classify_last_checker_raw(last_checker_raw)
    hit_cap = (
        coder_loop_total_iterations is not None
        and coder_loop_max_iterations is not None
        and coder_loop_total_iterations >= coder_loop_max_iterations
    )

    if hit_cap:
        if kind == CheckerGateFailureKind.CONTRACT_FAILED:
            reason_extra = (
                f"\nThe coder/checker loop reached its configured maximum "
                f"({coder_loop_total_iterations} of {coder_loop_max_iterations} iterations) "
                "while the checker kept returning `\"status\": \"failed\"` (tests or build still failing)."
            )
        elif kind == CheckerGateFailureKind.NO_VALID_CONTRACT:
            reason_extra = (
                f"\nThe coder/checker loop reached its configured maximum "
                f"({coder_loop_total_iterations} of {coder_loop_max_iterations} iterations) "
                "without a parseable checker JSON line containing `\"status\": \"passed\"`."
            )
        elif kind == CheckerGateFailureKind.CHECKER_INFRA:
            reason_extra = (
                f"\nThe coder/checker loop reached its configured maximum "
                f"({coder_loop_total_iterations} of {coder_loop_max_iterations} iterations) "
                "while the checker reported tooling or infrastructure errors "
                '(JSON with `"status": "error"` and `"scope": "checker"`).'
            )
        else:
            reason_extra = (
                f"\nThe coder/checker loop reached its configured maximum "
                f"({coder_loop_total_iterations} of {coder_loop_max_iterations} iterations)."
            )
    else:
        reason_extra = ""

    if kind == CheckerGateFailureKind.CONTRACT_FAILED:
        hint = checker_failure_hint_one_line(last_checker_raw or "") or ""
        hint_block = f"\nSummary from last checker JSON: {hint}\n" if hint else ""
        body = (
            "\nThe Smelters orchestration did not complete successfully: the PR/reviewer "
            "steps were not run because the checker gate never opened.\n"
            "The checker produced a valid JSON contract with `\"status\": \"failed\"` "
            "(tests and/or build errors). The PR path stays closed until a later iteration "
            "emits a final JSON line with `\"status\": \"passed\"`.\n"
            f"{hint_block}"
        )
    elif kind == CheckerGateFailureKind.NO_VALID_CONTRACT:
        body = (
            "\nThe Smelters orchestration did not complete successfully: the PR/reviewer "
            "steps were not run because the checker gate never opened.\n"
            "The last checker output did not contain an accepted JSON line with a "
            '`"status"` field (`"passed"` or `"failed"`). '
            "For opencode, subprocess exit code 0 is not the gate — only that JSON line is.\n"
        )
    elif kind == CheckerGateFailureKind.EMPTY:
        body = (
            "\nThe Smelters orchestration did not complete successfully: the PR/reviewer "
            "steps were not run because the checker gate never opened.\n"
            "No checker step content was captured from the workflow event log, so the "
            "failure mode could not be classified. Check earlier stderr/stdout for step or "
            "workflow errors.\n"
        )
    elif kind == CheckerGateFailureKind.CHECKER_INFRA:
        body = (
            "\nThe Smelters orchestration did not complete successfully: the PR/reviewer "
            "steps were not run because the checker gate never opened.\n"
            "The checker reported a tooling or infrastructure problem "
            '(final JSON line with `"status": "error"` and `"scope": "checker"`), '
            "not a failing test suite. Fix the checker environment or model configuration; "
            "the PR path opens only after a `\"status\": \"passed\"` line.\n"
        )
    else:
        body = (
            "\nThe Smelters orchestration did not complete successfully: the PR/reviewer "
            "steps were not run because the checker gate never opened.\n"
            "Unexpected: last captured checker output parses as `\"status\": \"passed\"` "
            "yet the PR-create step did not run — treat as an internal/workflow inconsistency "
            "and inspect Agno run events for this session.\n"
        )

    text = (
        "\n"
        + "=" * 72
        + "\nSMELTERS FLOW FAILED\n"
        + "=" * 72
        + body
        + reason_extra
        + "\n"
        + f"Resume state (checker output + metadata) was written to:\n  {resume_file}\n\n"
        + "Suggested re-run (same task and project; higher --max-iterations; --resume "
        "loads the saved checker output for the first coder pass):\n  "
        + suggested_command
        + "\n"
        + "=" * 72
        + "\n"
    )
    print(text, file=file, end="")

from __future__ import annotations

import re
from argparse import Namespace
from io import StringIO
from pathlib import Path

from src.smelters_flow_failure import (
    build_smelters_rerun_cli_command,
    print_smelters_flow_failed_banner,
)


def test_build_smelters_rerun_cli_includes_resume_and_max_iterations() -> None:
    args = Namespace(
        coder=None,
        checker=None,
        reviewer=None,
        coder_model="sonnet",
        checker_model="sonnet",
        head_branch=None,
        pr_title=None,
        pr_body_file=None,
        github_token_env="GITHUB_TOKEN",
        task_context_mode="inline",
        debug_logging=False,
    )
    cmd = build_smelters_rerun_cli_command(
        args,
        task_path=Path("tasks/DemoApp/x.md"),
        project_path=Path("projects/DemoApp"),
        agent_config_file=None,
        repo="org/repo",
        base_branch="main",
        suggested_max_iterations=8,
        include_resume_flag=True,
    )
    assert "--resume" in cmd
    assert re.search(r"--max-iterations\s+8", cmd) or "--max-iterations 8" in cmd


def test_build_smelters_rerun_cli_includes_debug_logging_when_set() -> None:
    args = Namespace(
        coder=None,
        checker=None,
        reviewer=None,
        coder_model="sonnet",
        checker_model="sonnet",
        head_branch=None,
        pr_title=None,
        pr_body_file=None,
        github_token_env="GITHUB_TOKEN",
        task_context_mode="inline",
        debug_logging=True,
    )
    cmd = build_smelters_rerun_cli_command(
        args,
        task_path=Path("tasks/DemoApp/x.md"),
        project_path=Path("projects/DemoApp"),
        agent_config_file=None,
        repo="org/repo",
        base_branch="main",
        suggested_max_iterations=8,
        include_resume_flag=False,
    )
    assert "--debug-logging" in cmd


def test_print_smelters_flow_failed_banner_writes_to_stream() -> None:
    buf = StringIO()
    print_smelters_flow_failed_banner(
        resume_file=Path("projects/DemoApp/.smelters/resume.json"),
        suggested_command="uv run python agno_orchestrator.py --resume",
        coder_loop_total_iterations=3,
        coder_loop_max_iterations=3,
        last_checker_raw=None,
        file=buf,
    )
    err = buf.getvalue()
    assert "SMELTERS FLOW FAILED" in err
    assert "uv run python agno_orchestrator.py --resume" in err

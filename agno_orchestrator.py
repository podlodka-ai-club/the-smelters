import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.db.sqlite import SqliteDb
from agno.workflow import Workflow
from agno.workflow.condition import Condition
from agno.workflow.loop import Loop
from agno.workflow.step import Step
from agno.workflow.types import HumanReview, OnReject, StepInput, StepOutput


_EPHEMERAL_DB_PATH: Optional[str] = None


def _ephemeral_db() -> SqliteDb:
    """SQLite for session metrics. Uses a per-process temp file so multiple
    connections see the same database (`:memory:` would give each connection
    its own empty DB and break session lookups). File is unlinked on exit."""
    global _EPHEMERAL_DB_PATH
    if _EPHEMERAL_DB_PATH is None:
        import atexit
        import tempfile
        f = tempfile.NamedTemporaryFile(prefix="agno-orchestrator-", suffix=".sqlite", delete=False)
        f.close()
        _EPHEMERAL_DB_PATH = f.name

        def _cleanup(p: str = _EPHEMERAL_DB_PATH) -> None:
            try:
                os.unlink(p)
            except OSError:
                pass

        atexit.register(_cleanup)
    return SqliteDb(db_file=_EPHEMERAL_DB_PATH)

from agno_agents.android_coder import make_android_coder
from agno_agents.code_checker import make_code_checker
from agno_agents.impl_agent import make_impl_agent
from agno_agents.lint_fix_agent import make_lint_fix_agent
from agno_agents.test_case_agent import make_test_case_agent
from agno_agents.test_run_agent import make_test_run_agent
from agno_agents.test_writer_agent import make_test_writer_agent
from agno_tools.claude_code_step import (
    get_claude_run_costs,
    make_claude_code_checker_step,
    make_claude_code_coder_step,
    reset_claude_run_costs,
)
from agno_tools.pr_comment_publisher import publish_review_comment
from agno_tools.pr_create_step import make_pr_create_step
from agno_tools.pr_reviewer_step import make_pr_reviewer_step
from shared.agent_base import load_config
from shared.checker_utils import last_json_line_with_checker_status
from src.smelters_flow_failure import build_smelters_rerun_cli_command, print_smelters_flow_failed_banner
from src.smelters_flow_state import checker_passed_from_content, pr_created_from_state
from src.smelters_post_run import summarize_smelters_post_run
from src.smelters_review_context import SmeltersReviewContext, resolve_smelters_review_context
from src.smelters_reviewer_backend import make_run_reviewer_backend
from src.smelters_resume import (
    clear_resume_file,
    merge_resume_into_task_markdown,
    read_resume_last_checker,
    resume_json_path,
    wrap_callable_coder_for_resume,
    write_resume_state,
)
from src.smelters_yaml import (
    merge_cli_backend_overrides,
    resolve_agent_config_path,
    resolve_smelters_backends_from_yaml,
)


@dataclass(frozen=True)
class ClassSpec:
    """Single-class TDD target — module, package, class derived from `**Module/Package/Class:**` headers."""
    module: str        # gradle reference, e.g. ":feature:favorites"
    package: str       # e.g. "com.aj.giphysearch.feature.favorites.ui"
    class_name: str    # e.g. "FavoritesViewModel"

    @property
    def module_path(self) -> str:
        return self.module.lstrip(":").replace(":", "/")

    @property
    def package_path(self) -> str:
        return self.package.replace(".", "/")

    @property
    def test_file_path(self) -> str:
        return f"{self.module_path}/src/test/kotlin/{self.package_path}/{self.class_name}Test.kt"

    @property
    def impl_file_path(self) -> str:
        return f"{self.module_path}/src/main/kotlin/{self.package_path}/{self.class_name}.kt"


_FIELD_RE = re.compile(r"\*\*([A-Za-z]+):\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
_SMELTERS_HEADER_RE = re.compile(r"^Project:\s*\S+", re.MULTILINE)


def detect_format(text: str) -> str:
    """class → has **Module/Package/Class:**; smelters → starts with `Project: <name>`; unknown otherwise."""
    if _FIELD_RE.search(text):
        fields = {m.group(1) for m in _FIELD_RE.finditer(text)}
        if {"Module", "Package", "Class"}.issubset(fields):
            return "class"
    if _SMELTERS_HEADER_RE.search(text):
        return "smelters"
    return "unknown"


def parse_class_spec(text: str, source: Path) -> ClassSpec:
    fields: Dict[str, str] = {m.group(1): m.group(2).strip() for m in _FIELD_RE.finditer(text)}
    missing = [k for k in ("Module", "Package", "Class") if k not in fields]
    if missing:
        sys.exit(
            f"ERROR: {source} is missing required field(s): {', '.join('**' + m + ':**' for m in missing)}\n"
            "Add lines like these near the top of the task file:\n"
            "    **Module:** `:feature:favorites`\n"
            "    **Package:** `com.aj.giphysearch.feature.favorites.ui`\n"
            "    **Class:** `FavoritesViewModel`\n"
        )
    module = fields["Module"]
    if not module.startswith(":"):
        module = f":{module}"
    return ClassSpec(module=module, package=fields["Package"], class_name=fields["Class"])


def derive_project_path(task_path: Path) -> Path:
    """tasks/DemoApp/6-foo.md → projects/DemoApp"""
    parts = task_path.parts
    if "tasks" not in parts:
        sys.exit(
            f"ERROR: cannot derive project path from {task_path}\n"
            "Either place the task under tasks/<ProjectName>/... or pass --project explicitly."
        )
    idx = parts.index("tasks")
    if idx + 1 >= len(parts) - 1:
        sys.exit(
            f"ERROR: task at {task_path} is not nested under tasks/<ProjectName>/. "
            "Pass --project explicitly."
        )
    project_name = parts[idx + 1]
    return Path("projects") / project_name


def lint_state_saver(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> StepOutput:
    content = step_input.previous_step_content or ""
    if session_state is not None:
        session_state["lint_result"] = content
    return StepOutput(content=content)


def test_state_saver(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> StepOutput:
    content = step_input.previous_step_content or ""
    if session_state is not None:
        session_state["test_result"] = content
    return StepOutput(content=content)


def _lint_failed(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> bool:
    state = session_state or {}
    return not (state.get("lint_result") or "").startswith("LINT_OK")


def _tests_failed(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> bool:
    state = session_state or {}
    return not (state.get("test_result") or "").startswith("TESTS_OK")


def build_workflow(task_dir: str, project_path: str, spec: ClassSpec, auto: bool = False) -> Workflow:
    test_case_agent = make_test_case_agent(
        task_path=task_dir,
        package=spec.package,
        class_name=spec.class_name,
    )
    test_writer_agent = make_test_writer_agent(
        project_path=project_path,
        package=spec.package,
        class_name=spec.class_name,
        test_file_path=spec.test_file_path,
    )
    impl_agent = make_impl_agent(
        project_path=project_path,
        package=spec.package,
        class_name=spec.class_name,
        impl_file_path=spec.impl_file_path,
        test_file_path=spec.test_file_path,
    )
    lint_fix_agent = make_lint_fix_agent(project_path=project_path, module=spec.module)
    test_run_agent = make_test_run_agent(
        project_path=project_path,
        module=spec.module,
        impl_file_path=spec.impl_file_path,
    )

    lint_loop = Loop(
        name="LintLoop",
        steps=[lint_fix_agent],
        max_iterations=3,
        end_condition=lambda outputs: bool(outputs) and (outputs[-1].content or "").startswith("LINT_OK"),
        forward_iteration_output=True,
    )

    test_loop = Loop(
        name="TestLoop",
        steps=[test_run_agent],
        max_iterations=3,
        end_condition=lambda outputs: bool(outputs) and (outputs[-1].content or "").startswith("TESTS_OK"),
        forward_iteration_output=True,
    )

    steps: list = [test_case_agent, test_writer_agent, impl_agent, lint_loop, lint_state_saver]

    if not auto:
        lint_fix_agent_gate = make_lint_fix_agent(project_path=project_path, module=spec.module)
        lint_human_review_step = Step(
            agent=lint_fix_agent_gate,
            human_review=HumanReview(
                requires_confirmation=True,
                confirmation_message=(
                    f"⚠️  detekt failed for {spec.module} after 3 attempts. "
                    "Please fix detekt errors manually, then confirm to continue."
                ),
                on_reject=OnReject.cancel,
            ),
        )
        steps.append(Condition(steps=[lint_human_review_step], evaluator=_lint_failed))

    steps.append(test_loop)
    steps.append(test_state_saver)

    if not auto:
        test_run_agent_gate = make_test_run_agent(
            project_path=project_path,
            module=spec.module,
            impl_file_path=spec.impl_file_path,
        )
        test_human_review_step = Step(
            agent=test_run_agent_gate,
            human_review=HumanReview(
                requires_confirmation=True,
                confirmation_message=(
                    f"⚠️  Tests failed for {spec.module} after 3 attempts. "
                    "Please fix the implementation manually, then confirm to continue."
                ),
                on_reject=OnReject.cancel,
            ),
        )
        steps.append(Condition(steps=[test_human_review_step], evaluator=_tests_failed))

    return Workflow(name="AgnoTDDWorkflow", steps=steps, db=_ephemeral_db())


def _fmt_int(n: int) -> str:
    """1234 -> '1 234'"""
    return f"{n:,}".replace(",", " ")


def _fmt_seconds(secs: float) -> str:
    if secs < 60:
        return f"{secs:.1f}s"
    m, s = divmod(int(secs), 60)
    return f"{m}m {s}s"


def run_with_metrics(workflow: Workflow, prompt: str, stream: bool = True) -> str:
    """Run the workflow, then print a wall-clock + token-usage summary.

    Returns the Agno ``session_id`` so callers can inspect ``get_last_run_output`` /
    ``get_session_state`` for Smelters post-run diagnostics.
    """
    session_id = str(uuid.uuid4())
    reset_claude_run_costs()
    start = time.time()
    try:
        workflow.print_response(prompt, session_id=session_id, stream=stream)
    finally:
        elapsed = time.time() - start
        try:
            metrics = workflow.get_session_metrics(session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            metrics = None
            metrics_err = str(exc)
        else:
            metrics_err = None
        claude_costs = get_claude_run_costs()  # [(label, usd), ...] from claude-cli steps

        print()
        print("┏━ Run Summary " + "━" * 60)
        print(f"┃  Wall-clock time:    {_fmt_seconds(elapsed)}")

        # Agno-tracked agents (Claude/Gemini via API)
        if metrics is None:
            if not claude_costs:
                print(f"┃  Token metrics:      unavailable ({metrics_err})")
        else:
            total_in = metrics.input_tokens or 0
            total_out = metrics.output_tokens or 0
            total = metrics.total_tokens or (total_in + total_out)
            cache_r = metrics.cache_read_tokens or 0
            cache_w = metrics.cache_write_tokens or 0
            reasoning = metrics.reasoning_tokens or 0
            if total or claude_costs:  # only show if anything happened
                print(f"┃  [Agno-tracked agents (API)]")
                print(f"┃    Tokens — input:   {_fmt_int(total_in)}")
                print(f"┃    Tokens — output:  {_fmt_int(total_out)}")
                if reasoning:
                    print(f"┃    Tokens — reason: {_fmt_int(reasoning)}")
                if cache_r or cache_w:
                    print(f"┃    Tokens — cache:  read {_fmt_int(cache_r)}, write {_fmt_int(cache_w)}")
                print(f"┃    Tokens — total:  {_fmt_int(total)}")
                if metrics.cost is not None:
                    print(f"┃    Cost (USD):     ${metrics.cost:.4f}")
                if metrics.details:
                    for model_id, model_metrics_list in metrics.details.items():
                        in_sum = sum((m.input_tokens or 0) for m in model_metrics_list)
                        out_sum = sum((m.output_tokens or 0) for m in model_metrics_list)
                        calls = len(model_metrics_list)
                        print(f"┃    {model_id}: {calls} calls, in={_fmt_int(in_sum)}, out={_fmt_int(out_sum)}")

        # claude-cli (subprocess) — costs reported by claude itself in the result event
        if claude_costs:
            total_cli_cost = sum(c for _, c in claude_costs)
            print(f"┃  [claude-cli (subscription)]")
            for label, cost in claude_costs:
                print(f"┃    {label}: ${cost:.4f}")
            print(f"┃    Total cost:     ${total_cli_cost:.4f} ({len(claude_costs)} call(s))")
        print("┗" + "━" * 73)
    return session_id


def _parse_checker_status(content: str) -> str:
    """Extract `status` from CodeChecker's last JSON line with a ``status`` field."""
    line = last_json_line_with_checker_status(content or "")
    if not line:
        return "unknown"
    try:
        parsed = json.loads(line)
    except (ValueError, TypeError, json.JSONDecodeError):
        return "unknown"
    if isinstance(parsed, dict):
        raw = parsed.get("status", "unknown")
        return raw if isinstance(raw, str) else "unknown"
    return "unknown"


def _checker_passed(outputs: List[Any]) -> bool:
    if not outputs:
        return False
    return _parse_checker_status(outputs[-1].content or "") == "passed"


def _checker_passed_from_step(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> bool:
    return checker_passed_from_content(step_input.previous_step_content or "")


def _pr_created_from_state(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> bool:
    return pr_created_from_state(session_state or {})


def _publish_review_comment_step(
    context: SmeltersReviewContext,
):
    def _step(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> StepOutput:
        state = session_state or {}
        pr_payload = state.get("pr_create_result") or {}
        review_payload = state.get("pr_reviewer_result") or {}
        pr_number = pr_payload.get("pr_number")
        if not isinstance(pr_number, int):
            return StepOutput(content='{"ok": false, "error": "missing PR number for comment publish"}')
        comment_body = (
            "## Reviewer result\n"
            f"- Approved: {review_payload.get('approved')}\n"
            f"- Notes: {review_payload.get('notes')}\n"
        )
        result = publish_review_comment(
            repo=context.repo,
            pr_number=pr_number,
            body=comment_body,
            token_env_name=context.github_token_env,
        )
        payload = {
            "ok": result.ok,
            "comment_id": result.comment_id,
            "action": result.action,
            "error": result.error,
        }
        if session_state is not None:
            session_state["pr_comment_result"] = payload.copy()
        return StepOutput(content=json.dumps(payload))

    _step.__name__ = "publish_review_comment_step"
    return _step


def _yaml_truthy(cfg: Dict[str, Any], key: str) -> bool:
    """Interpret optional YAML boolean flags (bool or common string forms)."""
    v = cfg.get(key)
    if v is True:
        return True
    if v is False or v is None:
        return False
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


def build_smelters_workflow(
    project_path: str,
    task_content: str,
    review_context: SmeltersReviewContext,
    coder_model: str = "claude",
    checker_backend: str = "gemini",
    reviewer_backend: str = "claude",
    max_iterations: int = 3,
    coder_claude_model: str = "sonnet",
    checker_claude_model: str = "sonnet",
    *,
    opencode_coder_model: str = "opencode/minimax-m2.5-free",
    opencode_checker_model: str = "opencode/ling-2.6-flash-free",
    opencode_reviewer_model: str = "opencode/nemotron-3-super-free",
    opencode_server_url: str = "",
    agent_timeout_secs: float = 7200.0,
    resume_checker_output: Optional[str] = None,
    debug_logging: bool = False,
) -> Workflow:
    """Two-step loop: coder writes tests + impl + RUN_TESTS.sh; checker runs the script.
    On failure the checker's JSON becomes input to the next coder iteration.

    Args:
        coder_model: coder backend:
          - "claude":     Agno Agent on Claude Sonnet 4.6 (needs ANTHROPIC_API_KEY)
          - "gemini":     Agno Agent on Gemini 2.5 Flash (needs GOOGLE_API_KEY)
          - "claude-cli": subprocess to `claude -p` (needs Claude Code logged in)
        checker_backend: checker backend:
          - "gemini":     Agno Agent on Gemini 2.5 Flash (needs GOOGLE_API_KEY)
          - "claude-cli": subprocess to `claude -p` (needs Claude Code logged in)
          - "opencode":   `opencode run` with ``opencode_checker_model`` from agent_config.yml
        coder_claude_model: model passed to `claude --model ...` when
            coder_model == 'claude-cli'. Aliases ("sonnet" [default], "opus", "haiku")
            or full IDs ("claude-sonnet-4-6"). Ignored for other backends.
        checker_claude_model: same as above but for checker (default "sonnet"; "haiku"
            is a great cheap pick for the checker phase).
        opencode_coder_model: ``opencode run --model`` id when coder_model == "opencode"
            (default from agent_config.yml).
        opencode_checker_model: ``opencode run --model`` id when checker_backend == "opencode".
        opencode_reviewer_model: ``opencode run --model`` id when reviewer_backend == "opencode".
        opencode_server_url: optional ``opencode serve`` attach URL for opencode coder/checker/reviewer.
        agent_timeout_secs: max seconds for each opencode coder or checker invocation.
        resume_checker_output: optional raw checker output from a prior failed run (``--resume``),
            injected into the first coder pass (task text for Agno agents, ``previous_step_content``
            for callable coders).
        debug_logging: when True, opencode coder/checker/reviewer subprocesses stream combined
            output to stdout while capturing the full transcript (same flag as Agno DEBUG loggers).
    """
    resume_seed = (resume_checker_output or "").strip() or None
    task_for_agent = (
        merge_resume_into_task_markdown(task_content, resume_seed)
        if resume_seed and coder_model in ("claude", "gemini")
        else task_content
    )

    if coder_model == "claude-cli":
        coder_step = make_claude_code_coder_step(
            project_path=project_path,
            task_content=task_content,
            model_alias=coder_claude_model,
        )
        if resume_seed:
            coder_step = wrap_callable_coder_for_resume(coder_step, resume_seed)
    elif coder_model == "opencode":
        from agno_tools.opencode_coder_step import make_opencode_coder_step

        coder_step = make_opencode_coder_step(
            project_path=project_path,
            task_content=task_content,
            model_id=opencode_coder_model,
            opencode_server_url=opencode_server_url,
            timeout_secs=agent_timeout_secs,
            stream_output=debug_logging,
        )
        if resume_seed:
            coder_step = wrap_callable_coder_for_resume(coder_step, resume_seed)
    else:
        coder_step = make_android_coder(
            project_path=project_path,
            task_content=task_for_agent,
            model=coder_model,
        )

    if checker_backend == "claude-cli":
        checker_step = make_claude_code_checker_step(
            project_path=project_path,
            model_alias=checker_claude_model,
        )
    elif checker_backend == "opencode":
        from agno_tools.opencode_checker_step import make_opencode_checker_step

        checker_step = make_opencode_checker_step(
            project_path=project_path,
            model_id=opencode_checker_model,
            opencode_server_url=opencode_server_url,
            timeout_secs=agent_timeout_secs,
            stream_output=debug_logging,
        )
    else:
        checker_step = make_code_checker(project_path=project_path)

    coder_checker_loop = Loop(
        name="CoderCheckerLoop",
        steps=[coder_step, checker_step],
        max_iterations=max_iterations,
        end_condition=_checker_passed,
        forward_iteration_output=True,
    )
    pr_create_step = make_pr_create_step(review_context)
    run_reviewer = make_run_reviewer_backend(
        opencode_reviewer_model,
        opencode_server_url=opencode_server_url,
        timeout_secs=300.0,
        stream_output=debug_logging,
    )
    pr_reviewer_step = make_pr_reviewer_step(
        review_context,
        backend=reviewer_backend,
        pr_number=None,
        pr_url=None,
        run_backend=run_reviewer,
    )
    comment_step = _publish_review_comment_step(review_context)

    steps = [
        coder_checker_loop,
        Condition(steps=[pr_create_step], evaluator=_checker_passed_from_step),
        Condition(steps=[pr_reviewer_step, comment_step], evaluator=_pr_created_from_state),
    ]
    return Workflow(name="AgnoWorkflow", steps=steps, db=_ephemeral_db())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestrator. Two pipelines: class-mode TDD (single Kotlin class) and smelters-mode (open-ended PRD).",
        epilog=(
            "Layout:\n"
            "    tasks/<Project>/<N>-<slug>.md   ← task spec\n"
            "    projects/<Project>/             ← target Gradle codebase\n"
            "\n"
            "Smelters mode (open-ended PRD) — task starts with `Project: <Name>`:\n"
            "    Loop x N: AndroidCoder writes tests + impl + RUN_TESTS.sh\n"
            "                  ⇣\n"
            "              CodeChecker runs RUN_TESTS.sh, parses TEST-*.xml\n"
            "                  ⇣ (if failed → JSON feedback to coder, retry)\n"
            "              done when status==passed or max iterations reached\n"
            "    Smelters coder/checker/reviewer backends default from agent_config.yml "
            "(CLI overrides).\n"
            "\n"
            "Class mode (single-class TDD) — task has `**Module/Package/Class:**` headers:\n"
            "    TestCase → TestWriter → Impl → LintLoop(detekt) → TestLoop(:module:test)\n"
            "    Coder/checker on Gemini 2.5 Flash. --auto disables human-review gates."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--agent-config",
        default=None,
        metavar="PATH",
        help=(
            "YAML config (Smelters backends, opencode model ids, timeouts). "
            "Default: agent_config.yml under $REPO_ROOT or current directory."
        ),
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Path to task .md file (e.g. tasks/DemoApp/6-favorites-bookmarks-system.md)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Path to target Gradle root. Default: auto-detected as projects/<Name> from --task path.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Run unattended — drop human-review gates (class mode only). "
            "If LintLoop or TestLoop hits its 3-iteration cap, the orchestrator finishes anyway "
            "(read the log to see whether LINT_OK / TESTS_OK was actually reached)."
        ),
    )
    parser.add_argument(
        "--coder",
        choices=("claude", "gemini", "claude-cli", "opencode"),
        default=None,
        help=(
            "Override Smelters coder backend (see agent_config.yml ``smelters_coder_backend``). "
            "'claude' = Agno+Sonnet 4.6 (needs ANTHROPIC_API_KEY). "
            "'gemini' = Agno+Gemini 2.5 Flash (needs GOOGLE_API_KEY). "
            "'claude-cli' = `claude -p`. "
            "'opencode' = `opencode run` with ``opencode_coder_model``."
        ),
    )
    parser.add_argument(
        "--checker",
        choices=("gemini", "claude-cli", "opencode"),
        default=None,
        help=(
            "Override Smelters checker backend (see ``smelters_checker_backend``). "
            "'gemini' = Agno+Gemini 2.5 Flash. "
            "'claude-cli' = `claude -p`. "
            "'opencode' = `opencode run` with ``opencode_checker_model``."
        ),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Max iterations of the coder ⇄ checker loop (smelters mode). Default: 3.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Smelters mode only: load ``projects/<Name>/.smelters/resume.json`` and inject "
            "``last_checker_output`` into the first coder iteration (task preamble for "
            "Claude/Gemini agents; ``previous_step_content`` for claude-cli/opencode coders). "
            "The file must exist (it is written when a run ends without opening the PR path)."
        ),
    )
    parser.add_argument(
        "--coder-model",
        default="sonnet",
        help=(
            "Model for the coder when --coder claude-cli. "
            "Aliases ('sonnet' [default], 'opus', 'haiku' → latest of each family) "
            "or full IDs ('claude-sonnet-4-6', 'claude-opus-4-7'). "
            "Ignored for --coder claude/gemini/opencode."
        ),
    )
    parser.add_argument(
        "--checker-model",
        default="sonnet",
        help=(
            "Model for the checker when --checker claude-cli. "
            "Aliases ('sonnet' [default], 'opus', 'haiku') or full IDs. "
            "'haiku' is a fine cheap pick — checker just runs a script and parses XML. "
            "Ignored unless --checker claude-cli (gemini and opencode use their own model selection)."
        ),
    )
    parser.add_argument(
        "--reviewer",
        choices=("claude", "opencode"),
        default=None,
        help=(
            "Override Smelters local reviewer (see ``smelters_reviewer_backend``). "
            "'opencode' = `opencode run` with ``opencode_reviewer_model``."
        ),
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub repository slug for PR/review integration in smelters mode (owner/name).",
    )
    parser.add_argument(
        "--base-branch",
        default="main",
        help="Base branch for PR creation in smelters mode (default: main).",
    )
    parser.add_argument(
        "--head-branch",
        default=None,
        help="Optional head branch for PR creation. If omitted, runtime may infer it.",
    )
    parser.add_argument(
        "--pr-title",
        default=None,
        help="Optional override for the PR title created by the smelters flow.",
    )
    parser.add_argument(
        "--pr-body-file",
        default=None,
        help="Optional markdown file path used as PR body in smelters mode.",
    )
    parser.add_argument(
        "--github-token-env",
        default="GITHUB_TOKEN",
        help=(
            "Env var name for GitHub token used by gh api (default: GITHUB_TOKEN). "
            "Optional: if unset, the orchestrator runs `gh auth token` when `gh` is logged in."
        ),
    )
    parser.add_argument(
        "--task-context-mode",
        choices=("inline", "path"),
        default="inline",
        help=(
            "How task context is passed to reviewer in smelters mode: "
            "'inline' embeds markdown text, 'path' passes task file path."
        ),
    )
    parser.add_argument(
        "--debug-logging",
        action="store_true",
        help=(
            "Enable Agno agent + workflow loggers at DEBUG, and stream combined stdout/stderr "
            "from opencode subprocess steps (Smelters coder/checker/reviewer) to the terminal "
            "while still capturing full output. Use 2>&1 | tee run.log to keep one file with "
            "streamed model output and subprocess logs."
        ),
    )
    args = parser.parse_args()

    agent_config_file = resolve_agent_config_path(args.agent_config)
    agent_cfg = load_config(config_path=agent_config_file)
    debug_logging = _yaml_truthy(agent_cfg, "debug_logging") or bool(
        getattr(args, "debug_logging", False)
    )
    if debug_logging:
        from agno.utils.log import set_log_level_to_debug

        set_log_level_to_debug(source_type=None)
        set_log_level_to_debug(source_type="workflow")

    task_path = Path(args.task)
    if not task_path.exists() or not task_path.is_file():
        sys.exit(f"ERROR: task file not found: {task_path}")

    text = task_path.read_text()
    fmt = detect_format(text)

    if fmt == "unknown":
        sys.exit(
            f"ERROR: cannot detect task format in {task_path}.\n"
            "Expected one of:\n"
            "  • smelters: first line `Project: <Name>` (open-ended PRD)\n"
            "  • class:    headers `**Module:**`, `**Package:**`, `**Class:**` (single-class TDD)\n"
        )

    project_path = Path(args.project) if args.project else derive_project_path(task_path)
    if not project_path.exists():
        sys.exit(f"ERROR: project not found at {project_path}")

    if fmt == "smelters":
        if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

        review_context = resolve_smelters_review_context(
            args,
            task_path=task_path,
            task_markdown=text,
            project_path=project_path,
        )

        yaml_backends = resolve_smelters_backends_from_yaml(agent_cfg)
        sm = merge_cli_backend_overrides(
            yaml_backends,
            coder_override=args.coder,
            checker_override=args.checker,
            reviewer_override=args.reviewer,
        )
        coder_backend, checker_backend, reviewer_backend = sm.coder, sm.checker, sm.reviewer

        opencode_coder_model = str(
            agent_cfg.get("opencode_coder_model") or "opencode/minimax-m2.5-free"
        )
        opencode_checker_model = str(
            agent_cfg.get("opencode_checker_model") or "opencode/ling-2.6-flash-free"
        )
        opencode_reviewer_model = str(
            agent_cfg.get("opencode_reviewer_model") or "opencode/nemotron-3-super-free"
        )
        opencode_server_url = str(agent_cfg.get("opencode_server_url") or "")
        agent_timeout_secs = float(agent_cfg.get("agent_timeout", 7200))

        if coder_backend == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit(
                "ERROR: ANTHROPIC_API_KEY is not set (required when Smelters coder is `claude`).\n"
                "  Set it, or set ``smelters_coder_backend`` / ``--coder`` to gemini, claude-cli, or opencode."
            )
        needs_claude_cli = coder_backend == "claude-cli" or checker_backend == "claude-cli"
        if needs_claude_cli:
            from shutil import which
            if not (which("claude") or os.environ.get("CLAUDE_BIN")):
                sys.exit(
                    "ERROR: claude CLI not found on PATH (required for any --coder/--checker claude-cli).\n"
                    "  Install Claude Code or set $CLAUDE_BIN to the binary path."
                )
        needs_opencode = (
            coder_backend == "opencode"
            or checker_backend == "opencode"
            or reviewer_backend == "opencode"
        )
        if needs_opencode:
            from shutil import which
            if not which("opencode"):
                sys.exit(
                    "ERROR: opencode CLI not found on PATH (required when any Smelters role uses opencode).\n"
                    "  Install opencode and ensure it is on PATH."
                )
        needs_google = coder_backend == "gemini" or checker_backend == "gemini"
        if needs_google and not (
            os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        ):
            sys.exit(
                "ERROR: GOOGLE_API_KEY or GEMINI_API_KEY is not set (required when coder or checker is `gemini`).\n"
                "  Get a key at https://aistudio.google.com/app/apikey, then export GOOGLE_API_KEY=…\n"
                "  Or switch ``smelters_*_backend`` / CLI flags to opencode or claude-cli."
            )

        coder_label = {
            "claude": "Claude Sonnet 4.6 (Agno API)",
            "gemini": "Gemini 2.5 Flash (Agno API)",
            "claude-cli": f"Claude Code CLI (`claude -p --model {args.coder_model}`, subscription auth)",
            "opencode": f"opencode (`opencode run --model {opencode_coder_model}`)",
        }[coder_backend]
        checker_label = {
            "gemini": "Gemini 2.5 Flash (Agno API)",
            "claude-cli": f"Claude Code CLI (`claude -p --model {args.checker_model}`, subscription auth)",
            "opencode": f"opencode (`opencode run --model {opencode_checker_model}`)",
        }[checker_backend]
        review_label = (
            f"opencode (`opencode run --model {opencode_reviewer_model}`)"
            if reviewer_backend == "opencode"
            else reviewer_backend
        )
        print(
            "[AgnoWorkflow]\n"
            f"  Config:  {agent_config_file}\n"
            f"  Task:    {task_path}\n"
            f"  Project: {project_path}\n"
            f"  Coder:   {coder_label}\n"
            f"  Checker: {checker_label}\n"
            f"  Repo:    {review_context.repo}\n"
            f"  PR base: {review_context.base_branch}\n"
            f"  PR head: {review_context.head_branch or '(infer)'}\n"
            f"  Token:   ${review_context.github_token_env}\n"
            f"  Context: {review_context.task_context_mode}\n"
            f"  Review:  {review_label}\n"
            f"  Loop:    Coder ⇄ Checker, max {args.max_iterations} iterations\n"
        )

        resume_path = resume_json_path(project_path)
        resume_checker_output: Optional[str] = None
        if args.resume:
            loaded = read_resume_last_checker(resume_path)
            if loaded is None:
                sys.exit(
                    f"ERROR: --resume requires a readable resume file at {resume_path}\n"
                    "  (It is written when a Smelters run ends without opening the PR path.)"
                )
            resume_checker_output = loaded

        workflow = build_smelters_workflow(
            project_path=str(project_path),
            task_content=text,
            review_context=review_context,
            coder_model=coder_backend,
            checker_backend=checker_backend,
            reviewer_backend=reviewer_backend,
            max_iterations=args.max_iterations,
            coder_claude_model=args.coder_model,
            checker_claude_model=args.checker_model,
            opencode_coder_model=opencode_coder_model,
            opencode_checker_model=opencode_checker_model,
            opencode_reviewer_model=opencode_reviewer_model,
            opencode_server_url=opencode_server_url,
            agent_timeout_secs=agent_timeout_secs,
            resume_checker_output=resume_checker_output,
            debug_logging=debug_logging,
        )
        session_id = run_with_metrics(workflow, "Begin work on the task spec embedded in your instructions.")
        summary = summarize_smelters_post_run(workflow, session_id)
        agent_config_for_cli = agent_config_file if agent_config_file.is_file() else None
        suggested_max = max(args.max_iterations + 5, 8)
        if summary.pr_create_step_ran:
            clear_resume_file(resume_path)
            sys.exit(0 if summary.pr_create_ok else 1)

        write_resume_state(
            resume_path,
            task_path=task_path,
            repo=review_context.repo,
            max_iterations=args.max_iterations,
            last_checker_output=summary.last_checker_raw or "",
        )
        rerun_cli = build_smelters_rerun_cli_command(
            args,
            task_path=task_path,
            project_path=project_path,
            agent_config_file=agent_config_for_cli,
            repo=review_context.repo,
            base_branch=review_context.base_branch,
            suggested_max_iterations=suggested_max,
            include_resume_flag=True,
        )
        print_smelters_flow_failed_banner(
            resume_file=resume_path,
            suggested_command=rerun_cli,
            coder_loop_total_iterations=summary.coder_loop_total_iterations,
            coder_loop_max_iterations=summary.coder_loop_max_iterations,
            last_checker_raw=summary.last_checker_raw,
        )
        sys.exit(1)

    # fmt == "class"
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit(
            "ERROR: GOOGLE_API_KEY is not set (required for class-mode TDD pipeline).\n"
            "  Get a key at https://aistudio.google.com/app/apikey, then export GOOGLE_API_KEY=…"
        )

    spec = parse_class_spec(text, task_path)
    print(
        "[AgnoTDDWorkflow]\n"
        f"  Task:    {task_path}\n"
        f"  Project: {project_path}\n"
        f"  Module:  {spec.module}\n"
        f"  Package: {spec.package}\n"
        f"  Class:   {spec.class_name}\n"
        f"  Test:    {spec.test_file_path}\n"
        f"  Impl:    {spec.impl_file_path}\n"
        f"  Mode:    {'AUTO (no human gates)' if args.auto else 'INTERACTIVE (human gates on failure)'}\n"
    )

    workflow = build_workflow(
        task_dir=str(task_path.parent),
        project_path=str(project_path),
        spec=spec,
        auto=args.auto,
    )
    prompt = (
        f"Implement {spec.package}.{spec.class_name} in module {spec.module}. "
        f"Spec: {task_path}. Project root: {project_path}."
    )
    run_with_metrics(workflow, prompt)


if __name__ == "__main__":
    main()
